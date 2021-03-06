
import datetime
from decimal import Decimal
import os
import random
import re
import string

import pytz
import transaction
from five import grok
import martian.util
from zope import schema
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from AccessControl import getSecurityManager
from AccessControl import Unauthorized
from Acquisition import aq_base
from zope.interface import alsoProvides
from zope.interface import Interface
from zope.component import getUtility
from zope.component import getMultiAdapter
from zope.component.hooks import getSite
from zope.app.content.interfaces import IContentType
from zope.app.container.interfaces import IObjectAddedEvent
from zope.event import notify
from zope.pagetemplate.pagetemplatefile import PageTemplateFile
from zope.lifecycleevent.interfaces import IObjectModifiedEvent
from zope.lifecycleevent import ObjectModifiedEvent
from plone.uuid.interfaces import IUUID
from plone.app.uuid.utils import uuidToObject
from plone.app.async.interfaces import IAsyncService
from plone.namedfile.field import NamedImage
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.permissions import ModifyPortalContent
from Products.CMFPlone.interfaces import IPloneSiteRoot
from plone.i18n.locales.countries import CountryAvailability
from plone.directives import dexterity, form
from plone.supermodel import model
from plone.dexterity.utils import createContentInContainer
from plone.formwidget.contenttree.source import PathSourceBinder
from plone.formwidget.contenttree.source import ObjPathSourceBinder
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.z3cform.interfaces import IWrappedForm
from z3c.form.browser.radio import RadioWidget
from collective.salesforce.fundraising.asyncfail import email_failure_from_portal
from mailsnake.exceptions import HTTPRequestException
from plone.namedfile.interfaces import IImageScaleTraversable
from collective.chimpdrill.utils import IMailsnakeConnection
from collective.simplesalesforce.utils import ISalesforceUtility
from collective.salesforce.fundraising.utils import get_settings
from collective.salesforce.fundraising.us_states import states_list
from collective.salesforce.fundraising.janrain.rpx import SHARE_JS_TEMPLATE
from collective.salesforce.fundraising.personal_campaign_page import IPersonalCampaignPage
from collective.salesforce.fundraising.utils import uencode

import logging
logger = logging.getLogger("Plone")

email_re = re.compile(
    r"^[A-Z0-9._%!#$%&'*+\-/=?^_`{|}~()]+"
    r"@[A-Z0-9]+([.\-][A-Z0-9]+)*\.[A-Z]{2,8}$", re.I)

def build_secret_key():
    return ''.join(random.choice(string.ascii_letters + string.digits) for x in range(32))


def queueJobWithDelay(length, func, context, *args, **kwargs):
    """Queue a job with a delay to avoid database conflicts."""
    if length == 'short':
        seconds = 10
    else:
        seconds = 20
    before = datetime.datetime.now(pytz.UTC)
    async = getUtility(IAsyncService)
    async.queueJobWithDelay(
        None, before + datetime.timedelta(seconds=seconds),
        func, context, *args, **kwargs)


@grok.provider(schema.interfaces.IContextSourceBinder)
def availableCampaigns(context):
    #campaign = context.get_fundraising_campaign()
    query = {
        "portal_type": [
            "collective.salesforce.fundraising.fundraising_campaign",
            "collective.salesforce.fundraising.personal_campaign_page",
        ],
        #"UUID": IUUID(campaign),
    }
    return ObjPathSourceBinder(**query).__call__(context)

class IDonation(model.Schema, IImageScaleTraversable):
    """
    A donation linked to its originating campaign and user
    """
    first_name = schema.TextLine(
        title=u"First Name",
        description=u"The donor's first name as submitted in the donation form",
        required=False,
    )

    last_name = schema.TextLine(
        title=u"Last Name",
        description=u"The donor's last name as submitted in the donation form",
        required=True,
    )

    email = schema.TextLine(
        title=u"Email",
        description=u"The donor's email as submitted in the donation form",
        required=False,
    )

    email_opt_in = schema.Bool(
        title=u"Email Opt In",
        description=u"The donor's selection for email opt in submitted in the donation form",
        required=True,
        default=False,
    )

    phone = schema.TextLine(
        title=u"Phone",
        description=u"The donor's phone number as submitted in the donation form",
        required=False,
    )

    address_street = schema.TextLine(
        title=u"Street Address",
        description=u"The donor's street address as submitted in the donation form",
        required=False,
    )

    address_city = schema.TextLine(
        title=u"City",
        description=u"The donor's city as submitted in the donation form",
        required=False,
    )

    address_state = schema.TextLine(
        title=u"State",
        description=u"The donor's state as submitted in the donation form",
        required=False,
    )

    address_zip = schema.TextLine(
        title=u"Zip",
        description=u"The donor's zip as submitted in the donation form",
        required=False,
    )

    address_country = schema.TextLine(
        title=u"Country",
        description=u"The donor's country as submitted in the donation form",
        required=False,
    )

    fingerprint = schema.TextLine(
        title=u"Fingerprint",
        description=u"The Stripe card fingerprint",
        required=False,
    )

    products = schema.List(
        title=u"Products",
        description=u"Format: ProductUID|Price|Quantity",
        required=False,
        value_type=schema.TextLine(),
    )

    stripe_customer_id = schema.TextLine(
        title=u"Stripe Customer ID",
        description=u"If this donation was made through a Stripe customer (typically for recurring), the id will be here",
        required=False,
    )

    stripe_plan_id = schema.TextLine(
        title=u"Stripe Plan ID",
        description=u"If this is a recurring donation, this is set to the ID of the Stripe plan",
        required=False,
    )

    is_receipt_sent = schema.Bool(
        title=u"Receipt Sent?",
        description=u"Was an email receipt sent for this donation?  NOTE: This is checked automatically by the system",
        required=False,
        default=False,
    )

    is_notification_sent = schema.Bool(
        title=u"Notification Sent to Fundraiser?",
        description=u"Was an email notification sent for this donation?  NOTE: This is checked automatically by the system",
    )

    is_added = schema.Bool(
        title=u"Added to Campaign?",
        description=u"Was this donation added to the totals for the campaign?  NOTE: This is checked automatically by the system",
        required=False,
        default=False,
    )

    synced_contact = schema.Bool(
        title=u"Salesforce Contact Synced?",
        required=False,
        default=False,
    )
    synced_recurring = schema.Bool(
        title=u"Salesforce Recurring Donation Synced?",
        required=False,
        default=False,
    )
    synced_opportunity = schema.Bool(
        title=u"Salesforce Donation Synced?",
        required=False,
        default=False,
    )
    synced_time = schema.Datetime(
        title=u"Salesforce Syncing Date",
        required=False
    )
    synced_index = schema.Int(
        title=u"Number of times Salesforce sync has been attempted",
        required=False,
        default=0
    )
    synced_products = schema.Bool(
        title=u"Salesforce Opportunity Products Synced?",
        required=False,
        default=False,
    )
    synced_contact_role = schema.Bool(
        title=u"Salesforce Opportunity Contact Role Synced?",
        required=False,
        default=False,
    )
    synced_campaign_member = schema.Bool(
        title=u"Salesforce Campaign Member Synced?",
        required=False,
        default=False,
    )
    subscribed_donor = schema.Bool(
        title=u"Subscribed to Donors List",
        required=False,
        default=False,
    )
    sf_honorary_type = schema.TextLine(
        title=u"Salesforce Honorary Type",
        description=u"The Honorary Type stored in Salesforce",
        required=False,
        default=u"",
    )

    model.load("models/donation.xml")
alsoProvides(IDonation, IContentType)

class ICreateOfflineDonation(model.Schema):
    """
    A schema of Donation without using model xml files so fields can be selected in forms
    """
    amount = schema.Int(
        title=u"Amount",
        description=u"",
        required=True,
    )

    form.widget(payment_method='z3c.form.browser.radio.RadioFieldWidget')
    payment_method = schema.Choice(
        title=u"Payment Method",
        description=u"Please select how you collected the offline gift.",
        values=[u'Cash', u'Check', 'Offline Credit Card'],
        required=True,
    )

    first_name = schema.TextLine(
        title=u"First Name",
        required=True,
    )

    last_name = schema.TextLine(
        title=u"Last Name",
        required=True,
    )

    email = schema.TextLine(
        title=u"Email",
        description=u"We will not automatically add this email to our email list",
        required=True,
    )

    phone = schema.TextLine(
        title=u"Phone",
        required=False,
    )

    address_street = schema.TextLine(
        title=u"Street Address",
        required=True,
    )

    address_city = schema.TextLine(
        title=u"City",
        required=True,
    )

    address_state = schema.TextLine(
        title=u"State",
        required=True,
    )

    address_zip = schema.TextLine(
        title=u"Zip",
        required=True,
    )

    address_country = schema.TextLine(
        title=u"Country",
        required=True,
    )


class ISalesforceDonationSync(Interface):
    def sync_to_salesforce():
        """ main method to sync donation to Salesforce.  Returns the salesforce ID for the opportunity """
    def get_products():
        """ get the products from the donation and convert to SF object structure """
    def create_opportunity():
        """ create the opportunity object for this donation in SF """
    def create_products():
        """ create opportunity products if needed """
    def create_opportunity_contact_role():
        """ create the opportunity contact role linking the contact with the opportunity """
    def create_campaign_member():
        """ create a campaign member object linking the contact to the campaign """

class IDonationReceipt(Interface):
    """ Callable class which renders the receipt as html """

class Donation(dexterity.Container):
    grok.implements(IDonation)

    def get_container(self):
        if not self.campaign_sf_id:
            return None
        site = getSite()
        pc = getToolByName(site, 'portal_catalog')
        res = pc.searchResults(
            sf_object_id=self.campaign_sf_id,
            portal_type = ['collective.salesforce.fundraising.fundraisingcampaign','collective.salesforce.fundraising.personalcampaignpage'],
        )
        if not res:
            return None
        return res[0].getObject()

    def get_friendly_date(self):
        return self.created().strftime('%B %d, %Y %I:%M%p %Z')

    def send_donation_receipt(self):
        settings = get_settings()
        res = ''
        
        try:
            res = self.send_email_thank_you()
        except HTTPRequestException as e:
            failure = {
                'func_name': 'send_donation_receipt',
                'func': '',
                'args': '',
                'kwargs': '',
                'portal_path': '',
                'context_path': repr(self),
                'userfolder_path': '',
                'user_id': '',
                'tb': e,
            }
            email_failure_from_portal(self, failure)
        
        if res:
            self.is_receipt_sent = True
        return res

        logger.warning('collective.salesforce.fundraising: Send Donation Receipt: No template found')

    def get_email_campaign_data(self):
        page = self.get_fundraising_campaign_page()
        return page.get_email_campaign_data()

    def get_email_thank_you_data(self):
        receipt = IDonationReceipt(self)()

        campaign = self.get_fundraising_campaign_page()
        campaign_thank_you = None
        if campaign.thank_you_message:
            campaign_thank_you = campaign.thank_you_message.output

        data = {
            'merge_vars': [
                {'name': 'first_name', 'content': self.first_name},
                {'name': 'last_name', 'content': self.last_name},
                {'name': 'amount', 'content': self.amount},
            ],
            'blocks': [
                {'name': 'receipt', 'content': receipt},
                {'name': 'campaign_thank_you', 'content': campaign_thank_you},
            ],
        }

        campaign_data = self.get_email_campaign_data()
        data['merge_vars'].extend(campaign_data['merge_vars'])
        data['blocks'].extend(campaign_data['blocks'])

        return data

    def get_email_honorary_data(self):
        # Use default values if none provided, useful for preview rendering
        honorary_first_name = self.honorary_first_name
        if not honorary_first_name:
            honorary_first_name = "FIRST_NAME"

        honorary_last_name = self.honorary_last_name
        if not honorary_last_name:
            honorary_last_name = "LAST_NAME"

        honorary_recipient_first_name = self.honorary_recipient_first_name
        if not honorary_recipient_first_name:
            honorary_recipient_first_name = "FIRST_NAME"

        honorary_recipient_last_name = self.honorary_recipient_last_name
        if not honorary_recipient_last_name:
            honorary_recipient_last_name = "LAST_NAME"

        data = {
            'merge_vars': [
                {'name': 'donor_first_name', 'content': self.first_name},
                {'name': 'donor_last_name', 'content': self.last_name},
                {'name': 'honorary_first_name', 'content': honorary_first_name},
                {'name': 'honorary_last_name', 'content': honorary_last_name},
                {'name': 'honorary_recipient_first_name', 'content': honorary_recipient_first_name},
                {'name': 'honorary_recipient_last_name', 'content': honorary_recipient_last_name},
                {'name': 'honorary_email', 'content': self.honorary_email},
                {'name': 'honorary_message', 'content': self.honorary_message},
            ],
            'blocks': [],
        }

        campaign_data = self.get_email_campaign_data()
        data['merge_vars'].extend(campaign_data['merge_vars'])
        data['blocks'].extend(campaign_data['blocks'])

        return data

    @property
    def synced_honorary_data(self):
        """
        Whether the Donation's honorary data is synced in Salesforce and Plone.

        """
        honor_type = self.honorary_type
        if honor_type is None:
            # If there is nothing to sync, it is synced
            return True
        return self.sf_honorary_type == honor_type

    def get_email_personal_page_donation_data(self):
        data = {
            'merge_vars': [
                {'name': 'amount', 'content': self.amount},
                {'name': 'donor_first_name', 'content': self.first_name},
                {'name': 'donor_last_name', 'content': self.last_name},
                {'name': 'donor_email', 'content': self.email},
            ],
            'blocks': [],
        }

        campaign_data = self.get_email_campaign_data()
        data['merge_vars'].extend(campaign_data['merge_vars'])
        data['blocks'].extend(campaign_data['blocks'])

        return data

    def get_email_recurring_receipt_data(self):
        campaign = self.get_fundraising_campaign_page()
        campaign_thank_you = None
        if campaign.thank_you_message:
            campaign_thank_you = campaign.thank_you_message.output

        update_url = '%s/@@stripe-update-customer-info?customer=%s' % (getSite().absolute_url(), self.stripe_customer_id)

        data = {
            'merge_vars': [
                {'name': 'first_name', 'content': self.first_name},
                {'name': 'last_name', 'content': self.last_name},
                {'name': 'amount', 'content': self.amount},
                {'name': 'update_url', 'content': update_url},
            ],
            'blocks': [
                {'name': 'campaign_thank_you', 'content': campaign_thank_you},
            ],
        }

        campaign_data = self.get_email_campaign_data()
        data['merge_vars'].extend(campaign_data['merge_vars'])
        data['blocks'].extend(campaign_data['blocks'])

        return data

    def get_email_template(self, field):
        campaign = self.get_fundraising_campaign()
        uuid = getattr(campaign, field, None)
        if not uuid:
            logger.warning('collective.salesforce.fundraising: get_email_template: No template configured for %s' % field)
            return

        template = uuidToObject(uuid)
        if not template:
            logger.warning('collective.salesforce.fundraising: get_email_template: No template found for %s' % field)
            return

        return template

    def send_email_thank_you(self):
        template = self.get_email_template('email_thank_you')
        if not template:
            return

        mail_to = self.email
        if not mail_to:
            logger.warning('collective.salesforce.fundraising: Send Thank You: No mail_to found')

        data = self.get_email_thank_you_data()

        return template.send(email = mail_to,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def render_email_thank_you(self):
        template = self.get_email_template('email_thank_you')
        if not template:
            return

        data = self.get_email_thank_you_data()

        return template.render(
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def send_email_honorary(self):
        if not self.honorary_email or self.honorary_notification_type != 'Email':
            # Skip if we have no email to send to
            return

        template = self.get_email_template('email_honorary')
        if not template:
            return

        mail_to = self.honorary_email
        data = self.get_email_honorary_data()

        # Send to the honorary notification email address
        template.send(email = mail_to,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

        # Send a copy to the donor
        template.send(email = self.email,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )


    def render_email_honorary(self):
        data = self.get_email_honorary_data()

        template = self.get_email_template('email_honorary')
        if not template:
            return

        return template.render(
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )


    def send_email_memorial(self):
        if not self.honorary_email or self.honorary_notification_type != 'Email':
            # Skip if we have no email to send to
            return

        if not self.honorary_type == 'Memorial':
            logger.warning('collective.salesforce.fundraising: Send Email Memorial: honorary_type is not Memorial')

        template = self.get_email_template('email_memorial')
        if not template:
            return

        mail_to = self.honorary_email
        data = self.get_email_honorary_data()

        # Send to the honorary notification email address
        template.send(email = mail_to,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

        # Send a copy to the donor
        template.send(email = self.email,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def render_email_memorial(self):
        template = self.get_email_template('email_memorial')
        if not template:
            return

        data = self.get_email_honorary_data()

        return template.render(
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def render_email_personal_page_donation(self):
        data = self.get_email_personal_page_donation_data()

        template = self.get_email_template('email_personal_page_donation')
        if not template:
            return

        return template.render(
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def send_email_personal_page_donation(self):
        page = self.get_fundraising_campaign_page()
        if not page.is_personal():
            # Skip if the donation was not to a personal campaign page
            return

        template = self.get_email_template('email_personal_page_donation')
        if not template:
            return

        person = page.get_fundraiser()
        if not person:
            return
        if not person.email:
            return

        mail_to = person.email
        data = self.get_email_personal_page_donation_data()

        # Record that the notification was sent
        self.is_notification_sent = True

        return template.send(email = mail_to,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def get_email_recurring_template(self, field):
        settings = get_settings()
        uuid = getattr(settings, field, None)
        if not uuid:
            logger.warning('collective.salesforce.fundraising: get_email_recurring_template: No template configured for %s' % field)
            return

        template = uuidToObject(uuid)
        if not template:
            logger.warning('collective.salesforce.fundraising: get_email_recurring_template: No template found for %s' % field)
            return

        return template

    def render_email_recurring_receipt(self):
        template = self.get_email_recurring_template('email_recurring_receipt')
        if not template:
            return

        data = self.get_email_recurring_receipt_data()
        return template.render(
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def send_email_recurring_receipt(self):
        template = self.get_email_recurring_template('email_recurring_receipt')
        if not template:
            return

        mail_to = self.email
        if not mail_to:
            logger.warning('collective.salesforce.fundraising: Email Recurring Receipt: no email address')
            return

        data = self.get_email_recurring_receipt_data()

        return template.send(email = mail_to,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def render_email_recurring_failed_first(self):
        template = self.get_email_recurring_template('email_recurring_failed_first')
        if not template:
            return

        data = self.get_email_recurring_receipt_data()
        return template.render(
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def send_email_recurring_failed_first(self):
        template = self.get_email_recurring_template('email_recurring_failed_first')
        if not template:
            return

        mail_to = self.email
        if not mail_to:
            logger.warning('collective.salesforce.fundraising: Email Failed First: no email address')
            return

        data = self.get_email_recurring_receipt_data()
        return template.send(email = mail_to,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def render_email_recurring_failed_second(self):
        template = self.get_email_recurring_template('email_recurring_failed_second')
        if not template:
            return

        data = self.get_email_recurring_receipt_data()

        return template.render(
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def send_email_recurring_failed_second(self):
        template = self.get_email_recurring_template('email_recurring_failed_second')
        if not template:
            return

        mail_to = self.email
        if not mail_to:
            logger.warning('collective.salesforce.fundraising: Email Failed Second: no email address')
            return

        data = self.get_email_recurring_receipt_data()
        return template.send(email = mail_to,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def render_email_recurring_failed_third(self):
        template = self.get_email_recurring_template('email_recurring_failed_third')
        if not template:
            return

        data = self.get_email_recurring_receipt_data()
        return template.render(
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def send_email_recurring_failed_third(self):
        template = self.get_email_recurring_template('email_recurring_failed_third')
        if not template:
            return

        mail_to = self.email
        if not mail_to:
            logger.warning('collective.salesforce.fundraising: Email Failed Third: no email address')
            return

        data = self.get_email_recurring_receipt_data()
        return template.send(email = mail_to,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def render_email_recurring_cancelled(self):
        template = self.get_email_recurring_template('email_recurring_cancelled')
        if not template:
            return

        data = self.get_email_recurring_receipt_data()
        return template.render(
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )

    def send_email_recurring_cancelled(self):
        template = self.get_email_recurring_template('email_recurring_cancelled')
        if not template:
            return

        mail_to = self.email
        if not mail_to:
            logger.warning('collective.salesforce.fundraising: Subscription Cancelled: no email address')
            return

        data = self.get_email_recurring_receipt_data()
        return template.send(email = mail_to,
            merge_vars = data['merge_vars'],
            blocks = data['blocks'],
        )


class ThankYouView(grok.View):
    grok.context(IDonation)
    grok.require('zope2.View')

    grok.name('view')
    grok.template('thank-you')

    def update(self):
        # check that either the secret_key was passed in the request or the user has modify rights
        key = self.request.form.get('key', None)
        if not key or key != self.context.secret_key:
            sm = getSecurityManager()
            if not sm.checkPermission(ModifyPortalContent, self.context):
                raise Unauthorized

        self.receipt = IDonationReceipt(self.context)()

        # Create a wrapped form for inline rendering
        from collective.salesforce.fundraising.forms import CreateDonationDonorQuote
        # Only show the form if a donor quote can be created
        if self.context.can_create_donor_quote():
            self.donor_quote_form = CreateDonationDonorQuote(self.context, self.request)
            alsoProvides(self.donor_quote_form, IWrappedForm)
            self.donor_quote_form.update()
            self.donor_quote_form.widgets.get('name').value = u'%s %s' % (self.context.first_name, self.context.last_name)
            if self.context.contact_sf_id and self.donor_quote_form.widgets.get('contact_sf_id'):
                self.donor_quote_form.widgets.get('contact_sf_id').value = unicode(self.context.contact_sf_id)
            self.donor_quote_form.widgets.get('key').value = unicode(self.context.secret_key)
            self.donor_quote_form.widgets.get('amount').value = int(self.context.amount)
            self.donor_quote_form_html = self.donor_quote_form.render()

        # Determine any sections that should be collapsed
        self.hide = self.request.form.get('hide', [])
        if self.hide:
            self.hide = self.hide.split(',')

    def render_janrain_share(self):
        settings = get_settings()
        comment = settings.thank_you_share_message
        if not comment:
            comment = ''

        amount_str = ''
        amount_str = u' $%s' % self.context.amount
        comment = comment.replace('{{ amount }}', str(self.context.amount))

        campaign = self.context.get_fundraising_campaign_page()
        if not campaign:
            return ''

        return SHARE_JS_TEMPLATE % {
            'link_id': 'share-message-thank-you',
            'url': campaign.absolute_url() + '?SOURCE_CODE=thank_you_share',
            'title': campaign.title.replace("'","\\'"),
            'description': campaign.description.replace("'","\\'"),
            'image': campaign.absolute_url() + '/@@images/image',
            'message': comment,
        }

class HonoraryMemorialView(grok.View):
    grok.context(IDonation)
    grok.require('zope2.View')

    grok.name('honorary-memorial-donation')

    form_template = ViewPageTemplateFile('donation_templates/honorary-memorial-donation.pt')

    def send_email(self):
        if self.context.honorary_type == 'Memorial':
            try:
                return self.context.send_email_memorial()
            except HTTPRequestException as e:
                failure = {
                    'func_name': 'send_email',
                    'func': '',
                    'args': '',
                    'kwargs': '',
                    'portal_path': '',
                    'context_path': repr(self.context),
                    'userfolder_path': '',
                    'user_id': '',
                    'tb': e,
                }
                email_failure_from_portal(self.context, failure)
        else:
            try:
                return self.context.send_email_honorary()
            except HTTPRequestException as e:
                failure = {
                    'func_name': 'send_email',
                    'func': '',
                    'args': '',
                    'kwargs': '',
                    'portal_path': '',
                    'context_path': repr(self.context),
                    'userfolder_path': '',
                    'user_id': '',
                    'tb': e,
                }
                email_failure_from_portal(self.context, failure)

    def render(self):
        # check that either the secret_key was passed in the request or the user has modify rights
        key = self.request.form.get('key', None)
        if not key or key != self.context.secret_key:
            sm = getSecurityManager()
            if not sm.checkPermission(ModifyPortalContent, self.context):
                raise Unauthorized

        self.receipt = IDonationReceipt(self.context)()

        # Handle POST
        if self.request['REQUEST_METHOD'] == 'POST':

            notification_type = self.request.form.get('honorary_notification_type', None)
            email = ''
            if notification_type == 'Email':
                email = (self.request.form.get('honorary_email') or '').strip()
                if email_re.match(email) is None:
                    # Redirect to an error page, allowing the user
                    # to press the back button and make corrections.
                    # This isn't ideal, but JS validation should normally
                    # stop users from getting here anyway.
                    return self.request.response.redirect(
                        '%s/email-error' % self.context.absolute_url(),
                        status=303)

            # Fetch values from the request
            self.context.honorary_type = self.request.form.get('honorary_type', None)
            self.context.honorary_notification_type = notification_type
            self.context.honorary_first_name = uencode(self.request.form.get('honorary_first_name', None))
            self.context.honorary_last_name = uencode(self.request.form.get('honorary_last_name', None))
            self.context.honorary_recipient_first_name = uencode(self.request.form.get('honorary_recipient_first_name', None))
            self.context.honorary_recipient_last_name = uencode(self.request.form.get('honorary_recipient_last_name', None))
            self.context.honorary_email = email
            self.context.honorary_street_address = uencode(self.request.form.get('honorary_street_address', None))
            self.context.honorary_city = uencode(self.request.form.get('honorary_city', None))
            self.context.honorary_state = uencode(self.request.form.get('honorary_state', None))
            self.context.honorary_zip = uencode(self.request.form.get('honorary_zip', None))
            self.context.honorary_country = uencode(self.request.form.get('honorary_country', None))
            self.context.honorary_message = uencode(self.request.form.get('honorary_message', None))

            # If there was an email passed and we're supposed to send an email, send the email
            if notification_type == 'Email':
                self.send_email()

            # Queue an update of the Donation to get honorary fields populated on the Opportunity in Salesforce
            queueJobWithDelay('normal', async_salesforce_sync_nomark, self.context)

            # Redirect on to the thank you page
            return self.request.response.redirect('%s?key=%s' % (self.context.absolute_url(), self.context.secret_key))

        self.countries = CountryAvailability().getCountryListing()
        self.countries.sort()

        self.states = states_list

        return self.form_template()


class EmailErrorView(grok.View):
    grok.context(IDonation)
    grok.require('zope2.View')
    grok.name('email-error')
    grok.template('email-error')


class HonoraryEmailView(grok.View):
    grok.context(IDonation)
    grok.name('honorary-email')

    def render(self):
        try:
            return self.context.render_email_honorary()
        except HTTPRequestException as e:
            failure = {
                'func_name': 'HonoraryEmailView',
                'func': '',
                'args': '',
                'kwargs': '',
                'portal_path': '',
                'context_path': repr(self.context),
                'userfolder_path': '',
                'user_id': '',
                'tb': e,
            }
            email_failure_from_portal(self.context, failure)

    def update(self):
        # check that either the secret_key was passed in the request or the user has modify rights
        key = self.request.form.get('key', None)
        if not key or key != self.context.secret_key:
            sm = getSecurityManager()
            if not sm.checkPermission(ModifyPortalContent, self.context):
                raise Unauthorized

class MemorialEmailView(grok.View):
    grok.context(IDonation)
    grok.name('memorial-email')

    def render(self):
        try:
            return self.context.render_email_memorial()
        except HTTPRequestException as e:
            failure = {
                'func_name': 'MemorialEmailView',
                'func': '',
                'args': '',
                'kwargs': '',
                'portal_path': '',
                'context_path': repr(self.context),
                'userfolder_path': '',
                'user_id': '',
                'tb': e,
            }
            email_failure_from_portal(self.context, failure)

    def update(self):
        # check that either the secret_key was passed in the request or the user has modify rights
        key = self.request.form.get('key', None)
        if not key or key != self.context.secret_key:
            sm = getSecurityManager()
            if not sm.checkPermission(ModifyPortalContent, self.context):
                raise Unauthorized

class SalesforceSyncView(grok.View):
    grok.context(IDonation)
    grok.require('zope2.View')
    grok.name('sync_to_salesforce')

    def render(self):
        async = getUtility(IAsyncService)
        async.queueJob(async_salesforce_sync, self.context)
        return 'OK: Queued for sync'

    def update(self):
        # check that either the secret_key was passed in the request or the user has modify rights
        key = self.request.form.get('key', None)
        if not key or key != self.context.secret_key:
            sm = getSecurityManager()
            if not sm.checkPermission(ModifyPortalContent, self.context):
                raise Unauthorized

class MarkAllDonationEmailsSent(grok.View):
    grok.context(IPloneSiteRoot)
    grok.name('mark-all-donation-emails-sent')

    def render(self):
        pc = getToolByName(self.context, 'portal_catalog')
        res = pc.searchResults(
            portal_type = 'collective.salesforce.fundraising.donation',
        )
        for b in res:
            donation = b.getObject()
            changed = False
            if not donation.is_receipt_sent:
                donation.is_receipt_sent = True
                changed = True
            if not donation.is_notification_sent:
                donation.is_notification_sent = True
                changed = True
            if changed:
                donation.reindexObject()


# Adapters

class DonationReceipt(grok.Adapter):
    grok.provides(IDonationReceipt)
    grok.context(IDonation)

    def __call__(self):
        settings = get_settings()
        self.organization_name = settings.organization_name
        self.campaign = self.context.get_fundraising_campaign()
        self.page = self.context.get_fundraising_campaign_page()
        self.donation_receipt_legal = self.campaign.donation_receipt_legal

        self.products = []
        if self.context.products:
            for product in self.context.products:
                price, quantity, product_uuid = product.split('|', 2)
                total = int(price) * int(quantity)
                product = uuidToObject(product_uuid)
                if not product:
                    continue
                if product.donation_only:
                    price = total
                    quantity = '-'
                self.products.append({
                    'price': price,
                    'quantity': quantity,
                    'product': product,
                    'total': total,
                })

        self.is_personal = self.page.is_personal()

        module = os.sys.modules[martian.util.caller_module()]
        _prefix = os.path.dirname(module.__file__)

        pt = PageTemplateFile('donation_templates/receipt.pt')
        return pt.pt_render({'view': self})

class SalesforceDonationSync(grok.Adapter):
    grok.provides(ISalesforceDonationSync)
    grok.context(IDonation)
    
    def mark_attempt(self):
        """mark the sync attempt on the donation
           used by a cronjob to know when to attempt another sync
        """
        self.context.synced_time = datetime.datetime.now()
        self.context.synced_index = self.context.synced_index + 1
        transaction.commit()

    def sync_to_salesforce(self, mark_att=True):
        if mark_att:
            self.mark_attempt()
        
        self.sfconn = getUtility(ISalesforceUtility).get_connection()
        self.campaign = self.context.get_fundraising_campaign()
        self.page = self.context.get_fundraising_campaign_page()
        self.pricebook_id = None
        self.settings = get_settings()

        if not self.context.synced_contact:
            self.sync_contact()
            transaction.commit()

        self.get_products()

        if not self.context.synced_recurring:
            self.upsert_recurring()
            transaction.commit()

        if not self.context.synced_opportunity or \
                not self.context.synced_honorary_data:
            self.upsert_opportunity()
            transaction.commit()

        # The following are only synced on the initial sync.  Logic needs to be added to query then
        # update as there is no external key that can be used for these.

        if self.context.honorary_type or not self.context.synced_products:
            self.create_products()
            transaction.commit()

        if not self.context.synced_contact_role:
            self.create_opportunity_contact_role()
            transaction.commit()

        if not self.context.synced_campaign_member:
            self.create_campaign_member()
            transaction.commit()

        self.context.reindexObject()
        return 'Successfully synced donation %s' % self.context.absolute_url()

    def sync_contact(self):
        # only upsert values that are non-empty to Salesforce to avoid overwritting existing values with null
        data = {
            'FirstName': self.context.first_name,
            'LastName': self.context.last_name,
            'Email': self.context.email,
            'Online_Fundraising_User__c' : True,
        }
        if self.context.email_opt_in:
            data['Email_Opt_In__c'] = self.context.email_opt_in
        if self.context.phone:
            data['HomePhone'] = self.context.phone
        if self.context.address_street:
            data['MailingStreet'] = self.context.address_street
        if self.context.address_city:
            data['MailingCity'] = self.context.address_city
        if self.context.address_state:
            data['MailingState'] = self.context.address_state
        if self.context.address_zip:
            data['MailingPostalCode'] = self.context.address_zip
        if self.context.address_country:
            data['MailingCountry'] = self.context.address_country

        res = self.sfconn.query("select id from contact where email = '%s' order by LastModifiedDate desc" % self.context.email)
        contact_id = None
        if res['totalSize'] > 0:
            # If contact exists, update
            contact_id = res['records'][0]['Id']

            res = self.sfconn.Contact.update(contact_id, data)
        else:
            # Otherwise create
            res = self.sfconn.Contact.create(data)

        # store the contact's Salesforce Id if it doesn't already have one
        if contact_id:
            self.context.contact_sf_id = contact_id
        else:
            self.context.contact_sf_id = res['id']

        self.context.synced_contact = True
        return res

    def get_products(self):
        self.products = []
        self.product_objs = {}

        if not self.context.products:
            return

        for line_item in self.context.products:
            price, quantity, product_uuid = line_item.split('|', 2)
            product = uuidToObject(product_uuid)
            self.products.append({
                'PricebookEntryId': product.pricebook_entry_sf_id,
                'UnitPrice': price,
                'Quantity': quantity,
            })
            self.product_objs[product.pricebook_entry_sf_id] = product

    def upsert_recurring(self):
        self.recurring_id = None

        if not self.context.stripe_customer_id:
            return

        page = self.context.get_fundraising_campaign_page()
        # If there is a recurring plan, create the Recurring Donation (1 API call)
        data = {
            'Name': self.context.title,
            'npe03__Amount__c': self.context.amount,
            'npe03__Recurring_Donation_Campaign__c': page.sf_object_id,
            'npe03__Contact__c': self.context.contact_sf_id,
            'npe03__Installment_Period__c': 'Monthly',
            'npe03__Open_Ended_Status__c': 'Open',
            'npe03__Paid_Amount__c': self.context.amount,
            'npe03__Total_Paid_Installments__c': 1,
        }

        # Add dates formatted in isoformat if they exist
        if self.context.payment_date:
            data['npe03__Last_Payment_Date__c'] = self.context.payment_date.isoformat()
        if self.context.next_payment_date:
            data['npe03__Next_Payment_Date__c'] = self.context.next_payment_date.isoformat()

        record_id = 'Stripe_Customer_ID__c/%s' % self.context.stripe_customer_id
        res = self.sfconn.npe03__Recurring_Donation__c.upsert(record_id, data)

        if res not in [201,204]:
            raise Exception('Upsert recurring donation failed with status %s' % res)

        self.context.synced_recurring = True

    def upsert_opportunity(self):
        # Create the Opportunity object and Opportunity Contact Role (2 API calls)
        if self.context.source_url is None:
            self.context.source_url = ''
        data = {
            'AccountId': self.settings.sf_individual_account_id,
            'Amount': self.context.amount,
            'Name': self.context.title,
            'StageName': self.context.stage,
            'CampaignId': self.page.sf_object_id,
            'Source_Campaign__c': self.context.source_campaign_sf_id,
            # Maximum length of a source url is 255 characters
            'Source_Url__c': self.context.source_url[:255],
            'Payment_Method__c': self.context.payment_method,
            'Is_Test__c': self.context.is_test == True,
            'Parent_Campaign__c': self.campaign.sf_object_id,
            'Secret_Key__c': self.context.secret_key,
            'Honorary_Type__c': self.context.honorary_type,
            'Honorary_First_Name__c': self.context.honorary_first_name,
            'Honorary_Last_Name__c': self.context.honorary_last_name,
            'Honorary_Contact__c': self.context.honorary_contact_sf_id,
            'Honorary_Message__c': self.context.honorary_message,
            'Honorary_Notification_Type__c': self.context.honorary_notification_type,
            'Honorary_Recipient_First_Name__c': self.context.honorary_recipient_first_name,
            'Honorary_Recipient_Last_Name__c': self.context.honorary_recipient_last_name,
            'Honorary_Email__c': self.context.honorary_email,
            'Honorary_Street_Address__c': self.context.honorary_street_address,
            'Honorary_City__c': self.context.honorary_city,
            'Honorary_State__c': self.context.honorary_state,
            'Honorary_Zip__c': self.context.honorary_zip,
            'Honorary_Country__c': self.context.honorary_country,
        }

        # Add dates formatted in isoformat if they exist
        if self.context.payment_date:
            data['CloseDate'] = self.context.payment_date.isoformat()

        if self.context.stripe_customer_id:
            data['npe03__Recurring_Donation__r'] = {
                'Stripe_Customer_ID__c': self.context.stripe_customer_id,
            }

        if self.products:
            products_configured = False
            for product in self.products:
                product_obj = self.product_objs.get(product['PricebookEntryId'])
                parent_form = product_obj.get_parent_product_form()
                if not products_configured:
                    if parent_form:
                        data['Name'] = '%s %s - %s' % (self.context.first_name, self.context.last_name, parent_form.title)
                    else:
                        product_obj = self.product_objs.get(product['PricebookEntryId'])
                        data['Name'] = '%s %s - %s (Qty %s)' % (self.context.first_name, self.context.last_name, product_obj.title, product['Quantity'])

                    if self.settings.sf_opportunity_record_type_product:
                        data['RecordTypeID'] = self.settings.sf_opportunity_record_type_product

                    # Set the pricebook on the Opportunity to the standard pricebook
                    data['Pricebook2Id'] = self.pricebook_id

                    # Set amount to 0 since the amount is incremented automatically by Salesforce
                    # when an OpportunityLineItem is created against the Opportunity
                    data['Amount'] = 0

                    products_configured = True

        else:
            # this is a one-time donation, record it as such if possible
            if self.settings.sf_opportunity_record_type_one_time:
                data['RecordTypeID'] = self.settings.sf_opportunity_record_type_one_time

        record_id = 'Success_Transaction_ID__c/%s' % self.context.transaction_id
        res = self.sfconn.Opportunity.upsert(record_id, data)

        if res not in [201,204]:
            raise Exception('Upsert opportunity failed with status %s' % res)

        self.context.sf_honorary_type = self.context.honorary_type
        self.context.synced_opportunity = True

    def create_products(self):
        if not self.products:
            return

        # Get the set of line items that already exist for this donation
        # in the Salesforce database.
        stmt = """\
            select PricebookEntryId, UnitPrice, Quantity
            from OpportunityLineItem
            where Opportunity.Success_Transaction_ID__c = '%s'
            """ % self.context.transaction_id
        res = self.sfconn.query(stmt)
        existent = set()
        for item in res['records']:
            existent.add((
                unicode(item['PricebookEntryId']),
                Decimal(item['UnitPrice']),
                int(item['Quantity']),
            ))

        for product in self.products:
            # Add an OpportunityLineItem unless it already exists.
            key = (
                unicode(product['PricebookEntryId']),
                Decimal(product['UnitPrice']),
                int(product['Quantity']),
            )
            if key in existent:
                continue

            product['Opportunity'] = {
                'Success_Transaction_ID__c': self.context.transaction_id,
            }
            res = self.sfconn.OpportunityLineItem.create(product)

            if not res['success']:
                raise Exception(res['errors'][0])

            # Note: it might be nice to also delete line items
            # to keep Salesforce in sync.  The API for doing that isn't
            # obvious though.

        self.context.synced_products = True

    def create_opportunity_contact_role(self):
        # FIXME: change to upsert
        res = self.sfconn.OpportunityContactRole.create({
            'Opportunity': {
                'Success_Transaction_ID__c': self.context.transaction_id,
            },
            'ContactId': self.context.contact_sf_id,
            'IsPrimary': True,
            'Role': 'Decision Maker',
        })

        if not res['success']:
            raise Exception(res['errors'][0])

        self.context.synced_contact_role = True

    def create_campaign_member(self):
        # Create the Campaign Member (1 API Call).  Note, we ignore errors on this step since
        # trying to add someone to a campaign that they're already a member of throws
        # an error.  We want to let people donate more than once.
        # Ignoring the error saves an API call to first check if the member exists
        if self.settings.sf_create_campaign_member:
            try:
                res = self.sfconn.CampaignMember.create({
                    'CampaignId': self.page.sf_object_id,
                    'ContactId': self.context.contact_sf_id,
                    'Status': 'Responded',
                })
            except:
                pass
            self.context.synced_campaign_member = True

# Event Handlers

# Salesforce sync
def async_salesforce_sync(donation):
    return ISalesforceDonationSync(donation).sync_to_salesforce()
def async_salesforce_sync_nomark(donation):
    return ISalesforceDonationSync(donation).sync_to_salesforce(mark_att=False)

@grok.subscribe(IDonation, IObjectAddedEvent)
def queueSalesforceSyncAdded(donation, event):
    queueJobWithDelay('short', async_salesforce_sync, donation)

@grok.subscribe(IDonation, IObjectModifiedEvent)
def queueSalesforceSyncModified(donation, event):
    queueJobWithDelay('normal', async_salesforce_sync, donation)

# Receipt email
def sendDonationReceipt(donation):
    if donation.is_receipt_sent:
        return 'Skipping send of email receipt as a receipt was already sent'
    return donation.send_donation_receipt()

@grok.subscribe(IDonation, IObjectAddedEvent)
def queueDonationReceiptAdded(donation, event):
    queueJobWithDelay('normal', sendDonationReceipt, donation)

@grok.subscribe(IDonation, IObjectModifiedEvent)
def queueDonationReceiptModified(donation, event):
    queueJobWithDelay('normal', sendDonationReceipt, donation)

# Subscribe donor to list
def mailchimpSubscribeDonor(donation):
    if donation.subscribed_donor:
        return 'Skipping, donor has already been subscribed to donors list'
    campaign = donation.get_fundraising_campaign()

    merge_vars = {
        'FNAME': donation.first_name,
        'LNAME': donation.last_name,
        'L_AMOUNT': donation.amount,
        'L_DATE': donation.get_friendly_date(),
        'L_RECEIPT': '%s?key=%s' % (donation.absolute_url(), donation.secret_key),
    }
    mc = getUtility(IMailsnakeConnection).get_mailchimp()

    res = mc.listSubscribe(
        id = campaign.email_list_donors,
        email_address = donation.email,
        merge_vars = merge_vars,
        update_existing = True,
        double_optin = False,
        send_welcome = False,
    )
    donation.subscribed_donor = True

    return res

@grok.subscribe(IDonation, IObjectAddedEvent)
def queueMailchimpSubscribeDonorAdded(donation, event):
    campaign = donation.get_fundraising_campaign()
    if not campaign.email_list_donors:
        # If no list is configured for donors, still mark that the step has been done
        # so it doesn't retry with every donation edit
        donation.subscribed_donor = True
        return 'Skipping, no donors list specified for campaign'

    queueJobWithDelay('normal', mailchimpSubscribeDonor, donation)

@grok.subscribe(IDonation, IObjectModifiedEvent)
def queueMailchimpSubscribeDonorModified(donation, event):
    campaign = donation.get_fundraising_campaign()
    if not campaign.email_list_donors:
        # If no list is configured for donors, still mark that the step has been done
        # so it doesn't retry with every donation edit
        donation.subscribed_donor = True
        return 'Skipping, no donors list specified for campaign'

    queueJobWithDelay('normal', mailchimpSubscribeDonor, donation)

# Personal campaign donation notification
def mailchimpSendPersonalCampaignDonation(donation):
    if getattr(donation, 'is_notification_sent', True):
        return 'Skipping: Donation notification already sent to fundraiser'
    campaign = donation.get_fundraising_campaign()
    uuid = getattr(campaign, 'email_personal_page_donation', None)
    if donation.offline:
        return 'Skipping, offline donation'
    return donation.send_email_personal_page_donation()

@grok.subscribe(IDonation, IObjectAddedEvent)
def queueMailchimpSendPersonalCampaignDonationAdded(donation, event):
    page = donation.get_fundraising_campaign_page()
    if not page.is_personal():
        # Skip if not a personal page
        return 'Skipping, not a personal page'

    queueJobWithDelay('normal', mailchimpSendPersonalCampaignDonation, donation)

#@grok.subscribe(IDonation, IObjectModifiedEvent)
#def queueMailchimpSendPersonalCampaignDonationModified(donation, event):
#    page = donation.get_fundraising_campaign_page()
#    if not page.is_personal():
#        # Skip if not a personal page
#        return 'Skipping, not a personal page'
#
#    async = getUtility(IAsyncService)
#    async.queueJob(mailchimpSendPersonalCampaignDonation, donation)

# Add to campaign totals.  This is best to do async to properly handle conflict errors
def addAmountToPage(donation):
    if getattr(donation, 'is_added', True):
        return 'Skipping: Donation already added to campaign'
    page = donation.get_fundraising_campaign_page()
    page.add_donation(donation.amount)
    donation.is_added = True

@grok.subscribe(IDonation, IObjectAddedEvent)
def queueAddAmountToPage(donation, event):
    queueJobWithDelay('normal', addAmountToPage, donation)
