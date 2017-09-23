# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
import re


class MailAliasRegex(models.Model):
    _name = 'mail.alias.regex'

    name = fields.Char('Name', help='Name of this Regex Rule', required=True)
    regex_expression = fields.Char('Regex Expression', help='Enter the Python compatible regex expression here.', required=True)
    active = fields.Boolean('Enabled', default=True)
    alias_id = fields.Many2one('mail.alias', 'Mail Alias')
    regex_exp_subject = fields.Char('Regex on Subject', help='If not empty, will act as a condition for executing this Regex rule. This regex expression will be matched against the subject of emails.')
    match_nth = fields.Integer('Match Nth Group', help='Matches the Nth group found during the regex matching. Matches the first if empty or 0.')
    regex_on = fields.Selection([('body', 'Body'), ('subject', 'Subject'), ('from', 'From')], 'Rule executes on ', default='body')
    regex_replace = fields.Boolean('Regex Replace', default=False, help='If enabled, will replace the matched data on the field selected.')
    field_id = fields.Many2one('ir.model.fields', 'Field', help='The field where the matched data will be stored.')
    model_id = fields.Many2one('ir.model', related='alias_id.alias_model_id')
    sequence = fields.Integer('Sequence')
    re_multiline = fields.Boolean('Multiline Match', default=False)
    re_dotall = fields.Boolean('Dot All', default=False)
    re_unicode = fields.Boolean('Unicode', default=True)
    re_locale = fields.Boolean('Locale', default=False)
    re_ignorecase = fields.Boolean('Ignore Case', default=False)
    test_block = fields.Text('Test Block (not stored)', store=False)
    test_returned = fields.Char('Test Result', store=False)

    @api.model
    def default_get(self, fields):
        rec = super(MailAliasRegex, self).default_get(fields)
        if self._context.get('alias_id'):
            alias_id = self._context.get('alias_id')
            rec['alias_id'] = alias_id
        if self._context.get('model_id'):
            model_id = self._context.get('model_id')
            rec['model_id'] = model_id

        return rec

    @api.one
    def validate_regex(self):
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
        try:
            re.compile(self.regex_expression.decode("string-escape"), _flags(self))
        except Exception, e:
            raise ValidationError('Regex expression: ' + e.message)

    @api.multi
    def write(self, vals):
        for regex in self:
            regex.validate_regex()
        return super(MailAliasRegex, self).write(vals)

    @api.onchange('test_block', 'regex_expression')
    @api.one
    def text_expression(self):
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
        self.test_returned = ''
        if self.regex_expression is False or self.regex_expression == '':
            return
        try:
            reg = re.compile(self.regex_expression.decode("string-escape"), _flags(self))
        except Exception, e:
            raise ValidationError('Regex expression: ' + e.message)
        if self.test_block:
            body_match = reg.findall(self.test_block)
            index = 0 if self.match_nth == 0 else self.match_nth - 1
            if len(body_match) >= self.match_nth + 1:
                self.test_returned = body_match[index]


class MailAlias(models.Model):
    _inherit = 'mail.alias'

    alias_regex_ids = fields.One2many('mail.alias.regex', 'alias_id', string='Regex Rules')

