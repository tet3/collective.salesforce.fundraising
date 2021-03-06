from z3c.form import interfaces

from zope import schema
from zope.interface import Interface
from plone.app.textfield import RichText

from zope.i18nmessageid import MessageFactory

_ = MessageFactory('collective.salesforce.fundraising')

class IFundraisingSettings(Interface):
    """Global settings for collective.salesforce.fundraising
    configuration registry and obtainable via plone.registry.
    """

    organization_name = schema.TextLine(
        title=_(u"Organization Name"),
        description=_(u"Enter your organization's official name.  This is used mostly on donation receipts."),
        required=True,
    )

    default_thank_you_message = schema.Text(
        title=_(u"Default Thank You Message"),
        description=_(u"The default Thank You Message for Fundraising Campaigns"),
        default=u"<p>Your donation was processed successfully.  Thank you for your support.</p>",
        required=True,
    )

    default_personal_appeal = schema.Text(
        title=_(u"Default Personal Appeal"),
        description=_(u"The default Personal Appeal for Personal Campaign Pages.  This can be overridden on a campaign by campaign basis"),
        default=u"<p>I am helping raise money for a great organization.  Please donate to help me reach my goal.</p>",
        required=True,
    )

    default_personal_thank_you = schema.Text(
        title=_(u"Default Personal Thank You"),
        description=_(u"The default Personal Thank You Message for Personal Campaign Pages"),
        default=u"<p>Thank you for your donation and for helping me reach my goal.</p>",
        required=True,
    )

    default_header_image_url = schema.TextLine(
        title=_(u"Default Header Image URL"),
        description=u"If provided, the specified image will be rendered as the header image for fundraising campaigns unless the campaign uses its header_image field to override the default setting.",
        required=False,
        
    )

    default_donation_form_header = schema.TextLine(
        title=_(u"Default Header for Donation Forms"),
        description=_(u"The text entered here will appear as a header above donation forms.  If left empty, the default value 'Make A Donation' will be used.  This value may be overridden by providing a value on a specific fundraising campaign."),
        default=u'',
        required=False,
    )

    default_donation_form_description = schema.Text(
        title=_(u"Default Description for Donation Forms"),
        description=_(u"The text entered here will be displayed above donation forms.  If left empty, no text will appear.  HTML is allowed. This value may be overridden by providing a value on a specific fundraising campaign"),
        default=u'',
        required=False,
    )

    default_donation_receipt_legal = schema.Text(
        title=_(u"Donation Receipt Legal Text"),
        description=_(u"Enter any legal text you want displayed at the bottom of html receipt.  For example, you might want to state that all donations are tax deductable and include the organization's Tax ID"),
        required=False,
    )

    ssl_seal = schema.Text(
        title=_(u"SSL Seal HTML Snippet"),
        description=_(u"If provided, this snippet of HTML will be inserted into the donation forms"),
        required=False,
    )

    thank_you_email_subject = schema.Text(
        title=_(u"Thank You Email Subject"),
        description=_(u"Enter the email subject for Thank You email messages with donation receipt"),
        required=False,
        default=_(u"Thank you for your donation")
    )

    thank_you_share_message = schema.Text(
        title=_(u"Thank You Share Message"),
        description=_(u"Enter the Share Message you want to present in the Share widget on the Thank You page after a donation.  {{ amount }} will be replaced with the amount"),
        required=False,
        default=_(u"I just donated ${{ amount }} to a great cause.  You should join me."),
    )

    default_campaign = schema.TextLine(
        title=_(u"Default Campaign UID"),
        description=_(u"The id of the default campaign for this site."),
        required=False,
    )

    email_header = schema.Text(
        title=_(u"Email Header HTML"),
        description=_(u"Enter any html you want to always render in the header of outbound emails."),
        required=False,
    )

    email_footer = schema.Text(
        title=_(u"Email Footer HTML"),
        description=_(u"Enter any html you want to always render in the footer of outbound emails."),
        required=False,
    )

    default_email_thank_you = schema.Choice(
        title=_(u"Email Template - Thank You Email"),
        description=_(u"Provide the path to the chimpdrill template to use by default for thank you emails."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.thank_you_templates',
    )

    default_email_honorary = schema.Choice(
        title=_(u"Email Template - Honorary Email"),
        description=_(u"Provide the path to the chimpdrill template to use by default for honorary notification emails."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.honorary_templates',
    )

    default_email_memorial = schema.Choice(
        title=_(u"Email Template - Memorial Email"),
        description=_(u"Provide the path to the chimpdrill template to use by default for memorial notification emails."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.memorial_templates',
    )

    default_email_personal_page_created = schema.Choice(
        title=_(u"Email Template - Personal Page Created Email"),
        description=_(u"Provide the path to the chimpdrill template to use by default for personal page created emails."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.personal_page_created_templates',
    )

    default_email_personal_page_donation = schema.Choice(
        title=_(u"Email Template - Personal Page Donation Email"),
        description=_(u"Provide the path to the chimpdrill template to use by default for personal page donation emails."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.personal_page_donation_templates',
    )

    email_recurring_receipt = schema.Choice(
        title=_(u"Email Template - Recurring Donation Receipt"),
        description=_(u"For recurring donations, the email template used to send receipts on recurring charges.  The first charge is sent the normal thank you email."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.recurring_receipt_templates',
    )

    email_recurring_failed_first = schema.Choice(
        title=_(u"Email Template - Recurring Payment Failed, First Time"),
        description=_(u"For recurring donations, the email template used to notify a donor that their recurring payment failed to process for the first time."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.recurring_receipt_templates',
    )

    email_recurring_failed_second = schema.Choice(
        title=_(u"Email Template - Recurring Payment Failed, Second Time"),
        description=_(u"For recurring donations, the email template used to notify a donor that their recurring payment failed to process for the second time."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.recurring_receipt_templates',
    )

    email_recurring_failed_third = schema.Choice(
        title=_(u"Email Template - Recurring Payment Failed, Third Time"),
        description=_(u"For recurring donations, the email template used to notify a donor that their recurring payment failed to process for the third time."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.recurring_receipt_templates',
    )

    email_recurring_cancelled = schema.Choice(
        title=_(u"Email Template - Recurring Donation Cancelled"),
        description=_(u"For recurring donations, the email template used to notify a donor that their recurring donation has been cancelled."),
        required=False,
        vocabulary=u'collective.salesforce.fundraising.recurring_receipt_templates',
    )

    default_stripe_recurring_plan = schema.TextLine(
        title=_(u"Default Stripe Recurring Plan"),
        description=_(u"Enter the ID of the default Stripe plan for recurring donations to be handled directly via Stripe"),
        required=False,
    )

    enable_share_via_email = schema.Bool(
        title=_(u"Enable Share via Email?"),
        description=_(u"If enabled, share messages will have a button to share via email which will send an email using Plone's built in mail configuration."),
        required=False,
        default=True,
    )

    default_donation_form = schema.Text(
        title=_(u"Default donation form"),
        description=_(u"The name of the form view to be used by default on a fundraising campaign to render the donation form.  This name must match a view's name on the campaign"),
        required=True,
        default=u'donation_form_stripe',
    )

    # FIXME: Add validation for the structure here
    donation_ask_levels = schema.List(
        title=_(u"Donation Ask Levels"),
        description=_(u"Enter sets of donation ask amounts one per line in the format ID|1,2,3,4,5,6 and use the value for ID in the url when calling the donation form"),
        default=[
            u"5|5,10,25,50,100,250",
            u"10|10,25,50,100,250,500",
            u"25|25,50,100,250,500,1000",
            u"50|50,100,250,500,1000,2500",
            u"100|100,500,1000,2500,5000,7500",
        ],
        value_type=schema.TextLine(),
    )

    default_donation_ask_one_time = schema.TextLine(
        title=_(u"Default One Time Donation Ask"),
        description=_(u"Enter the ID of the default Donation Ask Level set to use for one time donations if no set is specified in the url"),
        default=u"25",
    )

    default_donation_ask_recurring = schema.TextLine(
        title=_(u"Default Recurring Donation Ask"),
        description=_(u"Enter the ID of the default Donation Ask Level set to use for recurring donations if no set is specified in the url"),
        default=u"10",
    )

    # FIXME: Add validation for the structure here
    product_ask_levels = schema.List(
        title=_(u"Product Quantity Ask Levels"),
        description=_(u"Enter sets of product quanity ask amounts one per line in the format ID|1,2,3,4,5,6 and use the value for ID in the url when calling the donation form"),
        default=[
            u"1|1,2,3,4,5,10",
            u"5|5,10,25,50,75,100",
        ],
        value_type=schema.TextLine(),
    )

    default_product_ask = schema.TextLine(
        title=_(u"Default Product Quantity Ask"),
        description=_(u"Enter the ID of the default Product Ask Level set to use for Donation Products if no set is specified in the url"),
        default=u"1",
    )

    default_fundraising_seals = schema.List(
        title=_(u"Default Fundraising Seals"),
        description=_(u"Enter the full physical path (from Zope root) to the default seals to display on Fundraising Campaigns"),
        value_type=schema.TextLine(),
        required=False,
    )

    sf_individual_account_id = schema.TextLine(
        title=_(u"Salesforce Individual AccountId"),
        description=_(u"The ID of the Account in Salesforce that represents Individuals in the \"bucket account\" model.  This is typically an account named Individual. This account will be used as the default account when creating the Opportuntity object in Salesforce for a donation"),
        required=True,
        default=u'',
    )

    sf_opportunity_record_type_one_time = schema.TextLine(
        title=_(u"Salesforce Opportunity Record Type ID - One Time Donations"),
        description=_(u"If provided, any Opportunities created from a one time donation will be created as the specified record type"),
        required=False,
        default=u'',
    )

    sf_opportunity_record_type_recurring = schema.TextLine(
        title=_(u"Salesforce Opportunity Record Type ID - Recurring Donations"),
        description=_(u"If provided, any Opportunities created from a recurring donation will be created as the specified record type"),
        required=False,
        default=u'',
    )

    sf_opportunity_record_type_product = schema.TextLine(
        title=_(u"Salesforce Opportunity Record Type ID = Donation Product Donations"),
        description=_(u"If provided, any Opportunities created from a donation product will be created as the specified record type"),
        required=False,
        default=u'',
    )

    sf_recurring_donation_record_type = schema.TextLine(
        title=_(u"Salesforce Recurring Donation Record Type ID"),
        description=_(u"If provided, any Recurring Donation profiles created from a recurring donation will be created as the specified record type"),
        required=False,
        default=u'',
    )

    sf_campaign_record_type = schema.TextLine(
        title=_(u"Salesforce Campaign Record Type ID - Fundraising Campaign"),
        description=_(u"If provided, any Campaigns in Salesforce created by creating a Fundraising Campaign in this site will be created as the specified record type"),
        required=False,
        default=u'',
    )

    sf_campaign_record_type_personal = schema.TextLine(
        title=_(u"Salesforce Campaign Record Type ID - Personal Campaign Page"),
        description=_(u"If provided, any Campaigns in Salesforce created by creating a Personal Campaign Page in this site will be created as the specified record type"),
        required=False,
        default=u'',
    )

    sf_campaign_record_type_share = schema.TextLine(
        title=_(u"Salesforce Campaign Record Type ID - Share Message"),
        description=_(u"If provided, any Campaigns in Salesforce created by creating a Share Message in this site will be created as the specified record type"),
        required=False,
        default=u'',
    )

    sf_create_campaign_member = schema.Bool(
        title=_(u"Create Salesforce Campaign Member on Donation?"),
        description=_(u"If checked, a Campaign Member will be created for the Contact after a donation.  If you're concerned about API usage limits, unchecking this will reduce the number of API calls to process a donation by 1.  This is useful if you either don't care about campaign members on your fundraising campaign (donations are already linked) or if you are using a trigger on Opportunity creation to create the Campaign Member in Salesforce."),
        default=True,
    )

    sf_standard_pricebook_id = schema.TextLine(
        title=_(u"Salesforce Standard Pricebook ID"),
        description = _(u"The Salesforce Record ID of the Standard Pricebook.  This value will be autopopulated if left empty."),
        default=u'',
        required=False,
    )

    janrain_api_key = schema.TextLine(
        title=_(u"Janrain API Key"),
        description=_(u"If provided, Janrain integration functionality will be turned on allowing for social login and social sharing"),
        required=False,
    )

    janrain_site_id = schema.TextLine(
        title=_(u"Janrain Site ID"),
        description=_(u"If you are using Janrain, the Site ID is the name of your instance. You can find it in the urls in the embed code provided through the Janrain control panel"),
        required=False,
    )

    janrain_sharing_app_id = schema.TextLine(
        title=_(u"Janrain App ID"),
        description=_(u"If you are using Janrain, enter the value for appId in the embed code provided for your sharing widget"),
        required=False,
    )

    janrain_use_extended_profile = schema.Bool(
        title=_(u"Janrain - Use extended profile?"),
        description=_(u"If checked, the auth_info call after authentication will attempt to fetch an extended profile which is only available in the paid versions."),
        required=False,
    )

    campaign_status_completion_threshold = schema.Int(
        title=_(u"Campaign Status Completion Threshold"),
        description = _(u"The percentage of campaign goal completion that should be reached before displaying status on campaign pages."),
        default=3,
        required=False,
    )

    personal_campaign_status_completion_threshold = schema.Int(
        title=_(u"Campaign Status Completion Threshold"),
        description = _(u"The percentage of personal campaign goal completion that should be reached before displaying status on personal campaign pages."),
        default=0,
        required=False,
    )

    async_error_email = schema.TextLine(
        title=_(u"Async Error Email Address"),
        description=_(u"Where to send emails about errors that happen in asynchronous jobs"),
        default=u'support@sixfeetup.com',
        required=False,
    )
