import scrapy  # scraping library, does all the heavy lifting
from scrapy.linkextractors import LinkExtractor  # library to extract links from a page

import os
import json
import re


class LegalDecisions(scrapy.Spider):
    # name has to be unique in my project
    name = 'legal_decisions_big'
    # directory where I want to save the scraped legal decisions
    save_dir = 'decisions_big'

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
        # traverse the DOM by using the CSS class hltitle and child elements that are links
        # the div above is needed to uniquely identify the attribute, would scrape all links on the website otherwise
        # .getall gives us all links that are a child of this div on the page
        for url in response.css('div.hltitel a::attr(href)').getall():
            # add the first part of the url to every link, because of horrible webdesign
            url_full = 'https://www.gesetze-bayern.de' + url

            # create a new request for every link
            yield scrapy.Request(url_full, self.parse_decision)

        # after parsing all links the spider should go to the next page
        # the link to the next page is always the last item of the pagination
        next_page = LinkExtractor(restrict_css='ul.pagination :last-child').extract_links(response)
        # as we got an list of all links of the pagination we have to select the last one to go to the next page
        next_page = next_page[len(next_page) - 1].url

        # as long as there is a next page crawl it
        if next_page is not None:
            yield scrapy.Request(next_page, self.parse_legal, dont_filter=True)

    # function to parse the legal decisions
    # just get the name, the title and the reasoning part of the decision and disregard everything else
    def parse_decision(self, response):
        # get the metadata from the doc metadata
        title = response.css('h1.titelzeile::text').get()
        meta_title = response.xpath('//div[@id="doc-metadata"]/div/div/b/text()').get()
        court = re.findall(r'[A-Za-zäöüÄÖÜ ]+,', meta_title)[0]
        decision_style = re.findall(r', [A-Za-z ]+ v\.', meta_title)[0]
        decision_date = re.findall(r'\d\d.\d\d.\d\d\d\d', meta_title)[0]
        decision_id = re.findall(r'– .+', meta_title)[0]
        meta_title = re.sub('/', '$', meta_title)

        # clean the metadata
        court = court[:len(court) - 1]
        decision_style = decision_style[2:len(decision_style) - 3]
        decision_id = decision_id[2:]

        # get meta data from the rsprbox
        # get all rsprboxzeile divs that are between a rsprboxueber that contains "nemkette" and a rsprboxueber that
        # either contains "chlagw" of "eits", because there are not always guiding guidelines but if they exists they
        # come before the keywords
        norm_chains = response.xpath(
            '//div[@class="rsprboxueber"][contains(.,"menkette")]/following-sibling::div[@class="rsprboxzeile"][following-sibling::div[@class="rsprboxueber"][contains(.,"chlagw") or contains(., "eits")]]/text()').getall()
        decision_guidelines = response.css('div.leitsatz::text').getall()
        decision_keywords = ""
        # all rsprboxzeile that follow on a rsprboxueber that contains "instan" and are followed by a rsprboxueber that
        # contains "undstell"
        lower_court = response.xpath(
            '//div[@class="rsprboxueber"][contains(.,"instan")]/following-sibling::div[@class="rsprboxzeile"][following-sibling::div[@class="rsprboxueber"][contains(., "undstell")]]/text()').getall()
        # quick and dirty fix for additional information that is mixed in the lower court, the code was ignoring the
        # contains for the following sibling from above, could not fix it otherwise
        if 'Revision zugelassen' in lower_court:
            lower_court.remove('Revision zugelassen')
        additional_information = ""
        decision_reference = ""

        # to not have null values in the JSON the response is checked for values before the values are assigned
        if response.xpath(
                '//div[@class="rsprboxueber"][contains(.,"lagwort")]/following-sibling::div[@class="rsprboxzeile"]/text()').get() is not None:
            decision_keywords = response.xpath(
                '//div[@class="rsprboxueber"][contains(.,"lagwort")]/following-sibling::div[@class="rsprboxzeile"]/text()').get()
        if response.xpath(
                '//div[@class="rsprboxueber"][contains(.,"eiterf")]/following-sibling::div[@class="rsprboxzeile"]/text()').get() is not None:
            additional_information = response.xpath(
                '//div[@class="rsprboxueber"][contains(.,"eiterf")]/following-sibling::div[@class="rsprboxzeile"]/text()').get()
        if response.xpath(
                '//div[@class="rsprboxueber"][contains(.,"undstell")]/following-sibling::div[@class="rsprboxzeile"]/text()').get() is not None:
            decision_reference = response.xpath(
                '//div[@class="rsprboxueber"][contains(.,"undstell")]/following-sibling::div[@class="rsprboxzeile"]/text()').get()

        # get the text from every div with the class 'absatz tenor'
        tenor = response.xpath(
            '//h2[contains(.,"enor")]/following-sibling::div/div[@class="absatz tenor"]/text()').getall()

        # get every div with the class absatz tatbestand that follows on a h2 that contains 'bestand'
        legal_facts = response.xpath(
            '//h2[contains(.,"bestand")]/following-sibling::div/div[@class="absatz tatbestand"]/text()').getall()

        # get every node after the h2 that contains 'ründe', it is saved to a list
        decision_reasons = response.xpath(
            '//h2[contains(.,"ründe")]/following-sibling::div/div[@class="absatz gruende"]/text()').getall()

        # save all components in a JSON file
        final_format = {
            'meta': {
                'meta_title': meta_title,
                'court': court,
                'decision_style': decision_style,
                'date': decision_date,
                'file_number': decision_id,
                'title': title,
                'norm_chains': norm_chains,
                'decision_guidelines': decision_guidelines,
                'keywords': decision_keywords,
                'lower_court': lower_court,
                'additional_information': additional_information,
                'decision_reference': decision_reference
            },
            'decision_text': {
                "tenor": tenor,
                "legal_facts": legal_facts,
                "decision_reasons": decision_reasons
            }
        }

        # save each decision as extra file and ensure the right encoding
        with open('{}/{}.json'.format(self.save_dir, meta_title), 'w', encoding='utf-8') as f:
            json.dump(final_format, f, ensure_ascii=False)

        yield
