import scrapy  # scraping library, does all the heavy lifting
from scrapy.linkextractors import LinkExtractor # library to extract links from a page

import os
import json
import re


class LegalDecisions(scrapy.Spider):

    # name has to be unique in my project
    name = 'legal_decisions_small'
    # directory where I want to save the scraped legal decisions
    save_dir = 'decisions'

    # this function starts the spider
    def start_requests(self):

        # if this is the first document of this kind, make a new directory
        if not os.path.exists(self.save_dir):
            os.mkdir(self.save_dir)

        # scraping starting point
        urls = ['https://www.gesetze-bayern.de/Search/Filter/DOKTYP/rspr']

        for url in urls:
            # in contrast to the return statement I do not only return a value to my caller but also retain enough state
            # information to pick up my function after the last yield run
            # the request should not be filtered because it gets redirected to the same URL
            # and this would be filtered out
            yield scrapy.Request(url, self.parse_legal, dont_filter=True)

    # callback function to handle the response, by selecting all links to decisions and then going to the next page
    def parse_legal(self, response):

        # response is an HTML document of the whole website
        # we traverse the DOM and get all list elements wit the class hitlistItem
        # .getall gives us all items that match the description
        for list_item in response.css('li.hitlistItem').getall():
            # if the list item is a judgment we consider it further
            if 'Urteil ' in list_item:
                # get the link of the judgment
                url = re.findall('href=".+"', list_item)[0]
                # cut the HTML
                url = url[6:len(url)-1]

                # add the first part of the url to every link
                url_full = 'https://www.gesetze-bayern.de' + url

                # create a new request for every link
                yield scrapy.Request(url_full, self.parse_decision)

        # after parsing all links the spider should go to the next page
        # the link to the next page is always the last item of the pagination
        next_page = LinkExtractor(restrict_css='ul.pagination :last-child').extract_links(response)
        # as we got an list of all links of the pagination we have to select the last one to go to the next page
        next_page = next_page[len(next_page)-1].url

        # as long as there is a next page crawl it
        if next_page is not None:
            yield scrapy.Request(next_page, self.parse_legal, dont_filter=True)

    # function to parse the legal decisions
    # just get the name, the title and the reasoning part of the decision and disregard everything else
    def parse_decision(self, response):

        # get the metadata from the doc metadata
        name = response.css('h1.titelzeile::text').get()
        meta_title = response.xpath('//div[@id="doc-metadata"]/div/div/b/text()').get()
        meta_title = re.sub('/', '$', meta_title)

        # search for a h2 that contains the text "ründe"
        # to drive scrapers nuts they decided to not be consistent with their headings
        # get everything after this h2
        reasoning = response.xpath(
            '//h2[contains(.,"ründe")]/following-sibling::div/div[@class="absatz gruende"]/text()').getall()
        # join the list to one string but keep the structure with new lines
        reasoning = ' \n '.join(reasoning)

        # put everything together in one JSON for later use
        final_format = {
            'title': meta_title,
            'name': name,
            'text': reasoning
        }

        # save each decision as extra file and ensure the right encoding
        with open('{}/{}.json'.format(self.save_dir, meta_title), 'w', encoding='utf-8') as f:
            json.dump(final_format, f, ensure_ascii=False)

        yield
