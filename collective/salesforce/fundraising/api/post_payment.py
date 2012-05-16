import urllib
from zope.publisher.browser import BrowserView
from Products.CMFCore.utils import getToolByName

class PostPayment(BrowserView):
    """
    Handles the post-success logging and redirect.  The third party form system 
    should redirect to this view and pass values
    """

    def __call__(self, campaign_id, amount, name, email, **kwargs):

        # Fetch the campaign by campaign_id
        pc = getToolByName(self.context, 'portal_catalog')
        res = pc.searchResults(sf_object_id = campaign_id)
        if not res:
            # FIXME - Raise an error instead of returning an error string
            return 'ERROR: No fundraising campaign was found with the id %s' % campaign_id
        campaign = res[0].getObject()

        # Add the donation's amount to the campaign and increment donations count
        if amount:
            # FIXME - This will error if non-numeric string passed as amount
            amount = int(amount)
            campaign.donations_total = campaign.donations_total + amount
            campaign.donations_count = campaign.donations_count + 1

            # If this is a child campaign and its parent campaign is the parent
            # in Plone, add the value to the parent's donations_total
            if hasattr(campaign, 'parent_sf_id'):
                parent = campaign.aq_parent()
                if parent.sf_id == campaign.parent_sf_id:
                    parent.donations_total = parent.donations_total + amount
                    parent.donations_count = parent.donations_count + 1

        # This is specific to Formstack.  The name field is a split field that comes through
        # as a combined value with urlencoding.  Check for this format and parse if so
        if name.find('%0Alast+%3D+') != -1:
            name = name.replace('first+%3D+','').replace('%0Alast+%3D+', ' ').replace

        urlargs = {
           'amount': amount,
           'form.widget.name': name,
           'form.widget.email': email,
        }

        # Redirect the user to the campaign's thank you page
        self.request.RESPONSE.redirect(campaign.absolute_url() + '/@@thank-you?' + urllib.urlencode(urlargs))
