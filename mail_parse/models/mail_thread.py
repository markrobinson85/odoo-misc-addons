# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
import re


class MailThread(models.Model):
    _inherit = 'mail.thread'

    """
    At this step, we have the message that's already been routed.
    
    This method will handle forwarded mail and alias regex rules processing.
    
    To enable forwarded mail processing, create a new system parameter with key 'mail.catchall.forwards' with value 'true'
    
    Mail processing only affects mail that wasn't routed to an existing thread.
    """
    @api.model
    def message_route_process(self, message, message_dict, routes):
        for model, thread_id, custom_values, user_id, alias in routes or ():
            # if model and alias are true, and thread_id is False.
            if model and alias and thread_id is 0:
                # Handle mail forwarding differently
                handle_forwards = self.env['ir.config_parameter'].sudo().get_param('mail.catchall.forwards')

                if str(handle_forwards).lower() in ['true', 'yes', '1', 't']:
                    if message_dict['subject'].upper().startswith('FW:') or message_dict['subject'].upper().startswith('FWD:'):
                        # And the message was forwarded by someone on the odoo domain alias
                        from_email = self._handle_forwarded_mail(message_dict)
                        partner = self.env['res.partner'].search([('email', '=ilike', from_email)])
                        if partner.id:
                            message_dict['author_id'] = partner.id
                        else:
                            message_dict.pop('author_id', None)
                        message_dict['email_from'] = from_email
                        message_dict['from'] = from_email
                if alias:
                    custom_values, message_dict = self._handle_regex(alias, message_dict, custom_values)

        thread_id = super(MailThread, self).message_route_process(message, message_dict, routes)

        return thread_id

    # Return custom values from regex parsing.
    def _handle_regex(self, alias, message_dict, custom_values):
        def _flags(regex):
            flags = 0
            if regex.re_multiline:
                flags = re.M
            if regex.re_dotall:
                flags |= re.S
            if regex.re_ignorecase:
                flags |= re.I
            if regex.re_unicode:
                flags |= re.U
            return flags

        for alias_rec in alias:
            for regex in alias_rec.alias_regex_ids:
                if regex.active is False:
                    continue
                # Compile the reg expression using flags from the regex rule.
                reg = re.compile(regex.regex_expression.decode("string-escape"), _flags(regex))
                # If there is a subject expression, parse that first.
                if regex.regex_exp_subject:
                    subject_match = re.search(regex.regex_exp_subject, message_dict['subject'])
                    # subject matches
                    if subject_match:
                        body_match = reg.findall(message_dict['body'])
                        custom_values, message_dict = self._process_body_match(regex, body_match, custom_values, message_dict)
                else:
                    # No subject match necessary.
                    body_match = reg.findall(message_dict['body'])
                    custom_values, message_dict = self._process_body_match(regex, body_match, custom_values, message_dict)

        return custom_values, message_dict

    # Process the match found, and try to process it depending on the field type.
    def _process_body_match(self, regex, body_match, custom_values, message_dict):
        def _is_integer(string):
            try:
                return int(string)
            except ValueError:
                return False

        def _is_float(string):
            try:
                return float(string)
            except ValueError:
                return False

        if body_match:
            index = 0 if regex.match_nth == 0 else regex.match_nth - 1
            # check if the nth match exists.
            if len(body_match) >= regex.match_nth + 1:
                #Handle many2many and one2many
                if regex.field_id.ttype in ['many2many', 'one2many']:
                    custom_tags = []
                    # Assume tags, and split by comma.
                    split_tags = body_match[index].split(',')
                    for tag in split_tags:
                        record = self.env[regex.field_id.relation].search([('name', '=ilike', tag.lstrip().rstrip().capitalize())], limit=1)
                        if record:
                            custom_tags.append((4, record.id))
                        # If this is for crm tags, create the tag if it doesn't exist.
                        elif record.id is False and regex.field_id.relation == 'crm.lead.tag':
                            custom_tags.append((0, 0, {'name': tag.lstrip().rstrip()}))
                    if len(custom_tags) > 0:
                        # If there are already a set of values for this field, we can add onto it.
                        if regex.field_id.name in custom_values:
                            custom_values[regex.field_id.name].extend(custom_tags)
                        else:
                            custom_values[regex.field_id.name] = custom_tags
                # Handle many2one
                elif regex.field_id.ttype == 'many2one':
                    # If country field, search for country by code or country
                    if regex.field_id.relation == 'res.country':
                        # Search country names and code for a match.
                        record = self.env[regex.field_id.relation].search(['|', ('name', '=ilike', body_match[index]), ('code', '=ilike', body_match[index])], limit=1)
                    # If state, search for country or code, but limit code searches to United States and Canada (To avoid state code clashes)
                    elif regex.field_id.relation == 'res.country.state':
                        # TODO: Fix state code searches being limited to just Canada and USA.
                        record = self.env[regex.field_id.relation].search(['|', ('name', '=ilike', body_match[index]), '&', ('code', '=ilike', body_match[index]), ('country_id', 'in', (235, 39))], limit=1)
                    # Everything else, search by name
                    else:
                        record = self.env[regex.field_id.relation].search([('name', '=ilike', body_match[index])], limit=1)
                    # If a record was found,
                    if record.id is not False:
                        custom_values[regex.field_id.name] = record.id
                # Handle integers
                elif regex.field_id.ttype == 'integer':
                    # If the match is an integer
                    if _is_integer(body_match[index]) is not False:
                        custom_values[regex.field_id.name] = _is_integer(body_match[index])
                # Handle float/monetary
                elif regex.field_id.ttype in ['float', 'monetary']:
                    # If the match is a float
                    if _is_float(body_match[index]) is not False:
                        custom_values[regex.field_id.name] = _is_float(body_match[index])
                # Handle boolean
                elif regex.field_id.ttype == 'boolean':
                    custom_values[regex.field_id.name] = body_match[index].lower() in ['true', 'yes', '1', 't']

                # Handle email, email_from, and update author_id of email if partner found.
                elif regex.field_id.name == 'email' or regex.field_id.name == 'email_from':
                    partner = self.env['res.partner'].search([('email', '=ilike', body_match[index])], limit=1)
                    if partner:
                        message_dict['author_id'] = partner.id
                    else:
                        message_dict.pop('author_id', None)
                    custom_values[regex.field_id.name] = body_match[index]
                # Handle binary fields, do nothing.
                elif regex.field_id.ttype in ['binary']:
                    # TODO: Handle binary processing on HTML emails?
                    return custom_values, message_dict
                # Handle other fields.
                else:
                    custom_values[regex.field_id.name] = body_match[index]
        return custom_values, message_dict

    def _handle_forwarded_mail(self, message_dict):
        match = re.search("@([\w.]+)", message_dict['email_from'])
        # Test if message_id already in system.
        if match != None:
            sender_domain = match.group(1)
            odoo_domain = self.env['ir.config_parameter'].sudo().get_param('mail.catchall.domain')
            # Handle a secondary domain alias.
            odoo_domain2 = self.env['ir.config_parameter'].sudo().get_param('mail.catchall.domain2')
            if sender_domain == odoo_domain or sender_domain == odoo_domain2:
                # Find FROM address for Windows Mail, Apple Mail, Thunderbird
                from_indexes = [m.start() for m in re.finditer('From: ', message_dict['body'])]
                if len(from_indexes) == 0:
                    # Handle forwards from HTML Outlook 2016
                    from_indexes = [m.start() for m in re.finditer('>From:<', message_dict['body'])]
                if len(from_indexes) > 0:
                    string_to_search = message_dict['body'][from_indexes[0]:from_indexes[0] + 500]
                    match_mail = re.search("mailto:([\w\-\.]+@\w[\w\-]+\.+[\w\-]+)", string_to_search)
                    if match_mail:
                        from_address = match_mail.group(1)
                        return from_address

        return message_dict['email_from']

