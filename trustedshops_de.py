import datetime
import hashlib
import json
import re

# from geopy import Nominatim

from src.bstsouecepkg.extract import Extract
from src.bstsouecepkg.extract import GetPages


class Handler(Extract, GetPages):
    base_url = 'https://www.trustedshops.de'
    NICK_NAME = base_url.split('//')[-1]
    fields = ['overview']
    overview = {}
    tree = None
    api = None

    header = {
        'User-Agent':
            'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
        'Accept':
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9;application/json',
        'accept-language': 'en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7',
        'Content-Type': 'application/json'
    }

    def getResultListFromResponse(self, response, type):
        if type == 'API':
            data = json.loads(response.content)
            result = []
            try:
                companies = data['data'][1]['data']['rowData']
                for company in companies:
                    code = company['cellData'][1]['value']
                    # name = company['name'].replace(' ', '-')
                    # link = f'https://www.princeedwardisland.ca/en/feature/pei-business-corporate-registry-original#/service/LegacyBusiness/LegacyBusinessView;e=LegacyBusinessView;business_number={code}'
                    result.append(code)
                return result
            except:
                return None

    def getpages(self, searchquery):
        result = []
        url = f'https://shop-search-api.trustedshops.com/shopsearch?searchTerm={searchquery}&page=0&targetMarket=DEU'
        self.get_working_tree_api(url, 'api')
        for shop in self.api['shops'][:11]:
            result.append('https://' + shop['profileUrl'])
        return result

    def get_by_xpath(self, xpath, removeDuplicates=True):
        try:
            el = self.tree.xpath(xpath)
        except Exception as e:
            print(e)
            return None
        if el:
            if type(el) == str or type(el) == list:
                el = [i.strip() for i in el]
                el = [i for i in el if i != '']
            if len(el) > 1 and type(el) == list and removeDuplicates:
                el = list(dict.fromkeys(el))
            return el
        else:
            return None

    def reformat_date(self, date, format):
        date = datetime.datetime.strptime(date.strip(), format).strftime('%Y-%m-%d')
        return date

    def fill_business_classifier(self, xpathCodes=None, xpathDesc=None, xpathLabels=None):
        res = []
        length = None
        if xpathCodes:
            codes = self.get_by_xpath(xpathCodes)
            length = len(codes)
        if xpathDesc:
            desc = self.get_by_xpath(xpathDesc)
            length = len(desc)
        if xpathLabels:
            labels = self.get_by_xpath(xpathLabels)
            length = len(labels)


        for i in range(length):
            temp = {
                'code': codes[i] if xpathCodes else '',
                'description': desc[i] if xpathDesc else '',
                'label': labels[i] if xpathLabels else ''
            }
            res.append(temp)
        if res:
            self.overview['bst:businessClassifier'] = res

    def get_post_addr(self, tree):
        addr = self.get_by_xpath(tree, '//span[@id="lblMailingAddress"]/..//text()', return_list=True)
        if addr:
            addr = [i for i in addr if
                    i != '' and i != 'Mailing Address:' and i != 'Inactive' and i != 'Registered Office outside NL:']
            if addr[0] == 'No address on file':
                return None
            if addr[0] == 'Same as Registered Office' or addr[0] == 'Same as Registered Office in NL':
                return 'Same'
            fullAddr = ', '.join(addr)
            temp = {
                'fullAddress': fullAddr if 'Canada' in fullAddr else (fullAddr + ' Canada'),
                'country': 'Canada',

            }
            replace = re.findall('[A-Z]{2},\sCanada,', temp['fullAddress'])
            if not replace:
                replace = re.findall('[A-Z]{2},\sCanada', temp['fullAddress'])
            if replace:
                torepl = replace[0].replace(',', '')
                temp['fullAddress'] = temp['fullAddress'].replace(replace[0], torepl)
            try:
                zip = re.findall('[A-Z]\d[A-Z]\s\d[A-Z]\d', fullAddr)
                if zip:
                    temp['zip'] = zip[0]
            except:
                pass
        # print(addr)
        # print(len(addr))
        if len(addr) == 4:
            temp['city'] = addr[-3]
            temp['streetAddress'] = addr[0]
        if len(addr) == 5:
            temp['city'] = addr[-4]
            temp['streetAddress'] = addr[0]
        if len(addr) == 6:
            temp['city'] = addr[-4]
            temp['streetAddress'] = ', '.join(addr[:2])

        return temp

    def get_address(self, xpath=None, zipPattern=None, key=None, returnAddress=False, addr=None):
        if xpath:
            addr = self.get_by_xpath(xpath)
        if key:
            addr = self.get_by_api(key)
        if addr:
            if type(addr) == list:
                addr = ', '.join(addr)
            if '\n' in addr:
                splitted_addr = addr.split('\n')
            if ', ' in addr:
                splitted_addr = addr.split(', ')

            addr = addr.replace('\n', ' ')
            addr = addr[0] if type(addr) == list else addr
            temp = {
                'fullAddress': addr,
                'country': 'Deutschland'
            }
            if zipPattern:
                zip = re.findall(zipPattern, addr)
                if zip:
                    temp['zip'] = zip[0]
            try:
                patterns = ['Suite\s\d+']
                for pattern in patterns:
                    pat = re.findall(pattern, addr)
                    if pat:
                        first_part = addr.split(pat[0])
                        temp['streetAddress'] = first_part[0] + pat[0]
            except:
                pass
            try:
                street = addr.split('Street')
                if len(street) == 2:
                    temp['streetAddress'] = street[0] + 'Street'
                temp['streetAddress'] = addr.split(',')[0]


                # if temp['streetAddress']:
                #     temp['streetAddress'] = splitted_addr[0]
            except:
                pass
            try:
                # city = addr.replace(temp['zip'], '')
                # city = city.replace(temp['streetAddress'], '')
                # city = city.replace(',', '').strip()
                # city = re.findall('[A-Z][a-z]+', city)
                temp['city'] = addr.split(', ')[-2].replace('.', '')
                # temp['fullAddress'] += f", {temp['city']}"
            except:
                pass
            temp['fullAddress'] += f', {temp["country"]}'
            temp['fullAddress'] = temp['fullAddress'].replace('.,', ',')
            if returnAddress:
                return temp
            self.overview['mdaas:RegisteredAddress'] = temp

    def get_prev_names(self, tree):
        prev = []
        names = self.get_by_xpath(tree,
                                  '//table[@id="tblPreviousCompanyNames"]//tr[@class="row"]//tr[@class="row"]//td[1]/text() | //table[@id="tblPreviousCompanyNames"]//tr[@class="row"]//tr[@class="rowalt"]//td[1]/text()',
                                  return_list=True)
        dates = self.get_by_xpath(tree,
                                  '//table[@id="tblPreviousCompanyNames"]//tr[@class="row"]//tr[@class="row"]//td[2]/span/text() | //table[@id="tblPreviousCompanyNames"]//tr[@class="row"]//tr[@class="rowalt"]//td[2]/span/text()',
                                  return_list=True)
        print(names)
        if names:
            names = [i for i in names if i != '']
        if names and dates:
            for name, date in zip(names, dates):
                temp = {
                    'name': name,
                    'valid_to': date
                }
                prev.append(temp)
        return prev

    def getFrombaseXpath(self, tree, baseXpath):
        pass

    def get_by_api(self, key):
        try:
            el = self.api[key]
            return el
        except:
            return None

    def fillField(self, fieldName, key=None, xpath=None, test=False, reformatDate=None):
        if xpath:
            el = self.get_by_xpath(xpath)
        if key:
            el = self.get_by_api(key)
        if test:
            print(el)
        if el:
            if len(el) == 1:
                el = el[0]
            el = self.reformat_date(el, reformatDate) if reformatDate else el
            if fieldName == 'vcard:organization-name':
                self.overview[fieldName] = el.split('(')[0].strip()

            if fieldName == 'hasActivityStatus':
                self.overview[fieldName] = el

            if fieldName == 'bst:registrationId':
                self.overview[fieldName] = el

            if fieldName == 'Service':
                self.overview[fieldName] = {'serviceType': el}

            if fieldName == 'regExpiryDate':
                self.overview[fieldName] = self.reformat_date(el, reformatDate) if reformatDate else el

            if fieldName == 'vcard:organization-tradename':
                self.overview[fieldName] = el.split('\n')[0].strip()

            if fieldName == 'bst:aka':
                names = el.split('\n')
                names = el.split(' D/B/A ')
                if len(names) > 1:
                    names = [i.strip() for i in names]
                    self.overview[fieldName] = names
                else:
                    self.overview[fieldName] = names

            if fieldName == 'lei:legalForm':
                self.overview[fieldName] = {
                    'code': '',
                    'label': el}


            if fieldName == 'map':
                self.overview[fieldName] = el[0] if type(el) == list else el

            if fieldName == 'previous_names':
                el = el.strip()
                el = el.split('\n')
                if len(el) < 1:
                    self.overview[fieldName] = {'name': [el[0].strip()]}
                else:
                    el = [i.strip() for i in el]
                    res = []
                    for i in el:
                        temp = {
                            'name': i
                        }
                        res.append(temp)
                    self.overview[fieldName] = res

            if fieldName == 'isIncorporatedIn':
                if reformatDate:
                    self.overview[fieldName] = self.reformat_date(el, reformatDate)
                else:
                    self.overview[fieldName] = el

            if fieldName == 'sourceDate':
                self.overview[fieldName] = self.reformat_date(el, '%d.%m.%Y')
            if fieldName == 'regExpiryDate':
                self.overview[fieldName] = self.reformat_date(el, '%m/%d/%Y')

            if fieldName == 'bst:description':
                self.overview[fieldName] = el

            if fieldName == 'hasURL' and el != 'http://':
                if 'http:' not in el:
                    el = 'http:' + el
                self.overview[fieldName] = el
            if fieldName == 'bst:email':
                self.overview['bst:email'] = el

            if fieldName == 'tr-org:hasRegisteredPhoneNumber':
                if type(el) == list and len(el) > 1:
                    el = el[0]
                self.overview[fieldName] = el

            if fieldName == 'agent':
                # print(el)
                self.overview[fieldName] = {
                    'name': el.split('\n')[0],
                    'mdaas:RegisteredAddress': self.get_address(returnAddress=True, addr=' '.join(el.split('\n')[1:]),
                                                                zipPattern='[A-Z]\d[A-Z]\s\d[A-Z]\d')
                }
            if fieldName == 'RegulationStatusEffectiveDate':
                self.overview['RegulationStatusEffectiveDate'] = el

            if fieldName == 'logo':
                self.overview['logo'] = el

    def fill_identifiers(self, xpathTradeRegistry=None, xpathOtherCompanyId=None):
        temp = {}
        if xpathTradeRegistry:
            trade = self.get_by_xpath(xpathTradeRegistry)
            if trade:
                temp['trade_register_number'] = re.findall('HR.*', trade[0])[0]
        if xpathOtherCompanyId:
            other = self.get_by_xpath(xpathOtherCompanyId)
            if other:
                temp['other_company_id_number'] = other


        if temp:
            self.overview['identifiers'] = temp

    def check_tree(self):
        print(self.tree.xpath('//text()'))

    def get_working_tree_api(self, link_name, type, method='GET', data=None):
        if type == 'tree':
            if data:
                self.tree = self.get_tree(link_name,
                                          headers=self.header, method=method, data=json.dumps(data))
            else:
                self.tree = self.get_tree(link_name,
                                          headers=self.header, method=method)
        if type == 'api':
            if data:
                self.api = self.get_content(link_name,
                                            headers=self.header, method=method, data=json.dumps(data))
            self.api = self.get_content(link_name,
                                        headers=self.header, method=method)
            self.api = json.loads(self.api.content)

    def fillRatingSummary(self, xpathRatingGroup=None, xpathRatings=None):
        temp = {}
        if xpathRatingGroup:
            group = self.get_by_xpath(xpathRatingGroup)
            if group:
                temp['rating_group'] = group[0]
        if xpathRatings:
            rating = self.get_by_xpath(xpathRatings)
            if rating:
                temp['ratings'] = rating[0].split(' ')[0]
        if temp:
            self.overview['rating_summary'] = [temp]

    def fillAgregateRating(self, xpathReview=None, xpathRatingValue=None):
        temp = {}
        if xpathReview:
            review = self.get_by_xpath(xpathReview)
            if review:
                temp['reviewCount'] = review[0].split(' ')[0]
        if xpathRatingValue:
            value = self.get_by_xpath(xpathRatingValue)
            if value:
                if len(value) % 2 != 1:
                    value.append(value[0])
                temp['ratingValue'] = ''.join(value)

        if temp:
            temp['@type'] = 'aggregateRating'
            self.overview['aggregateRating'] = temp

    def fillReviews(self, xpathReviews=None, xpathRatingValue=None, xpathDate=None, xpathDesc=None, xpathAuthor=None):
        res = []
        try:
            reviews = self.tree.xpath(xpathReviews)
            for i in range(len(reviews)):
                temp = {}
                if xpathRatingValue:
                    ratingsValues = len(self.tree.xpath(f'//async-list//review[{i+1}]' + xpathRatingValue))
                    if ratingsValues:
                        temp['reviewRating'] = {'ratingValue': str(ratingsValues)}

                if xpathDate:
                    date = self.tree.xpath(f'//async-list//review[{i+1}]' + xpathDate)
                    if date:
                        temp['datePublished'] = date[0].split('T')[0]

                if xpathDesc:
                    desc = self.tree.xpath(f'//async-list//review[{i+1}]' + xpathDesc)
                    if desc:
                        temp['description'] = desc[0]
                if xpathAuthor:
                    author = self.tree.xpath(f'//async-list//review[{i+1}]' + xpathAuthor)
                    if author:
                        author = [i for i in author if i != '\xa0']
                        temp['author'] = ' '.join(author)
                if temp:
                    res.append(temp)
        except:
            pass
        if res:
            self.overview['review'] = res




    def get_overview(self, link_name):
        self.overview = {}
        self.get_working_tree_api(link_name, 'tree')
        #print(self.tree.xpath('//rewiew-header'))
        try:
            self.fillField('vcard:organization-name', xpath='//div[1]/text()[contains(., "Kontakt")]/../following-sibling::div[1]//text()')
        except:
            return None

        self.overview['isDomiciledIn'] = 'DE'
        #self.check_tree()
        text = ', '.join(self.tree.xpath('//text()'))
        #rint(text)
        try:
            logo = re.findall('profile_logoFullURL.+http.+jp.?g', text)[0].split(';')[-1]
            #print(logo)
            self.overview['logo'] = logo
        except:
            pass


        self.fillField('logo', xpath='//shop-logo//img/@src')

        self.overview['bst:sourceLinks'] = [link_name]
        self.fillField('hasActivityStatus', xpath='//div[1]/text()[contains(., "Status:")]/../following-sibling::div[1]//span/text()')
        self.fillField('bst:aka', xpath='//span[@class="shop-name"]/text()')
        self.fillField('hasURL',
                       xpath='//a/text()[contains(., "Zur Webseite")]/../@href')
        self.fillField('bst:email',
                      xpath='//div/@class[contains(., "email")]/..//a/text()')
        self.fill_business_classifier(xpathDesc='//categories//span/text()')
        self.get_address(xpath='//div/@class[contains(., "address")]/../div//text()', zipPattern='\d\d\d\d\d+')
        self.fillField('bst:description', xpath='//h2/@class[contains(., "section-headline")]/../following-sibling::div[1]//text()')
        self.fillField('tr-org:hasRegisteredPhoneNumber',
                                      xpath='//div/@class[contains(., "phone")]/..//a/text()')

        self.overview['regulator_name'] = 'Trustedshops.de'
        self.overview['regulator_url'] = self.base_url
        self.overview['RegulationStatus'] = 'Authorised'
        self.fillField('RegulationStatusEffectiveDate', xpath='//span/text()[contains(., "zertifiziert seit:")]/../following-sibling::span[2]/text()', reformatDate='%d.%m.%y')
        self.fill_identifiers(xpathTradeRegistry='//div/text()[contains(., "Handelsregister")]/../following-sibling::div[1]/span/text()')
        self.overview['bst:registryURI'] = link_name
        self.overview['@source-id'] = self.NICK_NAME
        self.fillRatingSummary(xpathRatingGroup='//div[@class="score-summary"]//div[@class="grade-name"]/text()',
                        xpathRatings='//h3/@class[contains(., "yearly-rating-count")]/../text()')
        self.fillAgregateRating(xpathReview='//div/@class[contains(., "total-rating-count")]/../text()',
                                xpathRatingValue='//div[@class="score-info"]//span/text()')
        self.fillReviews(xpathRatingValue='//rating-stars/span/@class[contains(., "active")]',
                         xpathReviews='//review',
                         xpathDate='//loading-line[2]/div/span/span/text()',
                         xpathDesc='//loading-line[1]/div/div/text()',
                         xpathAuthor='//a/@class[contains(., "author-info")]/..//span//text()')



        print(self.overview['review'])
        #exit()




        # self.fillField('bst:aka',
        #                xpath='//div[@class="sectionHeader"]/text()[contains(., "Contact Information")]/../following-sibling::div[1]//tr[1]/td[2]/text()')
        #
        # self.get_address(
        #     xpath='//div[@class="sectionHeader"]/text()[contains(., "Address")]/../following-sibling::div[1]//text()',
        #     zipPattern='\d\d\d\d\d+')
        # self.fillField('isIncorporatedIn',
        #                xpath='//td/text()[contains(., "Effective Date")]/../following-sibling::td/text()',
        #                reformatDate='%m/%d/%Y')
        # # self.fillField('bst:description',
        #                xpath='//div[@class="sectionHeader"]/text()[contains(., "Purpose")]/../following-sibling::div[1]/text()')
        # self.overview['registeredIn'] = 'Mississippi'
        #
        # self.fillField('identifiers',
        #                xpath='//div[@class="sectionHeader"]/text()[contains(., "Filing Information")]/../following-sibling::div[1]//td/text()[contains(., "Filing Number")]/../following-sibling::td/text()')
        # self.fillField('bst:registrationId',
        #                xpath='//div[@class="sectionHeader"]/text()[contains(., "Filing Information")]/../following-sibling::div[1]//td/text()[contains(., "Filing Number")]/../following-sibling::td/text()')
        # if self.overview['bst:registrationId']:
        #     self.overview['bst:registrationId'] = self.overview['bst:registrationId']
        # self.overview['regulator_name'] = 'Michal watson - Mississippi Secretary of State'
        # self.overview['regulatorAddress'] = {
        #     'fullAddress': 'New Capitol Room 105 Jackson, Mississippi 39201, United state',
        #     'city': 'Jackson',
        #     'country': 'United States'
        # }
        # self.overview['regulator_url'] = 'https://www.sos.ms.gov/contact-us/capitol-office'
        # self.overview['RegulationStatus'] = 'Active'
        # self.overview[
        #     'bst:registryURI'] = 'https://charities.sos.ms.gov/online/portal/ch/page/charities-search/Portal.aspx#'
        # self.overview['Service'] = {
        #     'areaServed': 'Mississippi',
        #     'serviceType': 'charity'
        # }
        # self.fillField('regExpiryDate',
        #                xpath='//div[@class="sectionHeader"]/text()[contains(., "Filing Information")]/../following-sibling::div[1]//td/text()[contains(., "Expiration Date")]/../following-sibling::td/text()')
        #
        # self.overview['@source-id'] = self.NICK_NAME
        # print(self.overview)
        # exit()

        # print(self.overview)
        # exit()
        # # self.overview['bst:sourceLinks'] = link_name
        #
        # self.fillField('vcard:organization-tradename', key='Trade Name(s)')

        # self.fillField('previous_names', key='Former Name(s)')
        # self.fillField('lei:legalForm', key='Business Type')

        #
        # self.fillField('Service', key='Business In')
        # self.fillField('agent', key='Chief Agent')
        # self.fillField('previous_names', key='Former Name(s)')
        # self.fillField('regExpiryDate', key='Expiry Date', reformatDate='%d-%b-%Y')
        # self.overview[
        #     'bst:registryURI'] = f'https://www.princeedwardisland.ca/en/feature/pei-business-corporate-registry-original#/service/LegacyBusiness/LegacyBusinessView;e=LegacyBusinessView;business_number={self.api["Registration Number"]}'
        # self.overview['@source-id'] = self.NICK_NAME

        # print(self.overview)
        # exit()
        # self.fillField('lei:legalForm', '//div/text()[contains(., "Legal form")]/../following-sibling::div//text()')
        # self.fillField('identifiers', '//div/text()[contains(., "Registry code")]/../following-sibling::div//text()')
        # self.fillField('map', '//div/text()[contains(., "Address")]/../following-sibling::div/a/@href')
        # self.fillField('incorporationDate', '//div/text()[contains(., "Registered")]/../following-sibling::div/text()')

        # self.fillField('bst:businessClassifier', '//div/text()[contains(., "EMTAK code")]/../following-sibling::div/text()')
        # self.get_business_class('//div/text()[contains(., "EMTAK code")]/../following-sibling::div/text()',
        #                         '//div/text()[contains(., "Area of activity")]/../following-sibling::div/text()',
        #                         '//div/text()[contains(., "EMTAK code")]/../following-sibling::div/text()')
        #
        # self.get_address('//div/text()[contains(., "Address")]/../following-sibling::div/text()',
        #                  zipPattern='\d{5}')
        #
        # self.overview['sourceDate'] = datetime.datetime.today().strftime('%Y-%m-%d')

        # self.overview['@source-id'] = self.NICK_NAME

        # print(self.overview)
        return self.overview

    # def get_officership(self, link_name):
    #     self.get_working_tree_api(link_name, 'api')
    #
    #     names = self.get_by_api('Officer(s)')
    #     if '\n' in names:
    #         names = names.split('\n')
    #     # roles = self.get_by_xpath(
    #     #     '//div/text()[contains(., "Right of representation")]/../following-sibling::div//tr/td[3]/text()')
    #
    #     off = []
    #     names = [names] if type(names) == str else names
    #     roles = []
    #     for name in names:
    #         roles.append(name.split(' - ')[-1])
    #     names = [i.split(' - ')[0] for i in names]
    #
    #     # roles = [roles] if type(roles) == str else roles
    #     for n, r in zip(names, roles):
    #         home = {'name': n,
    #                 'type': 'individual',
    #                 'officer_role': r,
    #                 'status': 'Active',
    #                 'occupation': r,
    #                 'information_source': self.base_url,
    #                 'information_provider': 'Prince Edward Island Corporate Registry'}
    #         off.append(home)
    #     return off

    # def get_documents(self, link_name):
    #     docs = []
    #     self.get_working_tree(link_name)
    #     docs_links = self.get_by_xpath('//div/a/text()[contains(., "PDF")]/../@href')
    #     docs_links = docs_links if type(docs_links) == list else [docs_links]
    #     docs_links = [f'{self.base_url}{i}' for i in docs_links]
    #     for doc in docs_links:
    #         temp = {
    #             'url': doc,
    #             'description': 'Summary of company details'
    #         }
    #         docs.append(temp)
    #     return docs

    # def get_financial_information(self, link_name):
    #     self.get_working_tree(link_name)
    #     fin = {}
    #     summ = self.get_by_xpath('//div/text()[contains(., "Capital")]/../following-sibling::div//text()')
    #     if summ:
    #         summ = re.findall('\d+', summ[0])
    #         if summ:
    #             fin['Summary_Financial_data'] = [{
    #                 'summary': {
    #                     'currency': 'Euro',
    #                     'balance_sheet': {
    #                         'authorized_share_capital': ''.join(summ)
    #                     }
    #                 }
    #             }]
    #     return fin
    # def get_shareholders(self, link_name):
    #
    #     edd = {}
    #     shareholders = {}
    #     sholdersl1 = {}
    #
    #     company = self.get_overview(link_name)
    #     company_name_hash = hashlib.md5(company['vcard:organization-name'].encode('utf-8')).hexdigest()
    #     self.get_working_tree_api(link_name, 'api')
    #     # print(self.api)
    #
    #     try:
    #         names = self.get_by_api('Shareholder(s)')
    #         if len(re.findall('\d+', names)) > 0:
    #             return edd, sholdersl1
    #         if '\n' in names:
    #             names = names.split('\n')
    #
    #         holders = [names] if type(names) == str else names
    #
    #         for i in range(len(holders)):
    #             holder_name_hash = hashlib.md5(holders[i].encode('utf-8')).hexdigest()
    #             shareholders[holder_name_hash] = {
    #                 "natureOfControl": "SHH",
    #                 "source": 'Prince Edward Island Corporate Registry',
    #             }
    #             basic_in = {
    #                 "vcard:organization-name": holders[i],
    #                 'isDomiciledIn': 'CA'
    #             }
    #             sholdersl1[holder_name_hash] = {
    #                 "basic": basic_in,
    #                 "shareholders": {}
    #             }
    #     except:
    #         pass
    #
    #     edd[company_name_hash] = {
    #         "basic": company,
    #         "entity_type": "C",
    #         "shareholders": shareholders
    #     }
    #     # print(sholdersl1)
    #     return edd, sholdersl1

    # def get_financial_information(self, link):
    #     data = {
    #         "searchType": "Charity_Services_IFSSearchResults",
    #         "entityName": link,
    #         "fileNumber": "",
    #         "filingClassId": "00000000-0000-0000-0000-000000000000"
    #     }
    #     url = 'https://charities.sos.ms.gov/online/Services/Common/IFSServices.asmx/ExecuteSearch'
    #     self.get_working_tree_api(url, 'api', method='POST', data=data)
    #     g = self.api['d']
    #     d = json.loads(g)
    #     self.api = d['Table'][0]
    #     url = f'https://charities.sos.ms.gov/online/portal/ch/page/charities-search/~/ViewXSLTFileByName.aspx?providerName=CH_EntityBasedFilingDetails&FilingId={self.api["FilingId"]}'
    #     self.get_working_tree_api(url, 'tree')
    #
    #     period = self.get_by_xpath(
    #         '//div[@class="sectionHeader"]/text()[contains(., "Financial Information")]/../following-sibling::div/div/text()')
    #     revenue = self.get_by_xpath(
    #         '//div[@class="sectionHeader"]/text()[contains(., "Financial Information")]/../following-sibling::div/div//td/text()[contains(., "Total Revenue")]/../following-sibling::td/text()')
    #     temp = {}
    #     if period and revenue:
    #         period = [self.reformat_date(i.split(': ')[-1], '%m/%d/%Y') for i in period]
    #         revenue = [i[2:] for i in revenue]
    #         tempList = []
    #         for p, r in zip(period, revenue):
    #             tempList.append({
    #                 'period': p,
    #                 'revenue': r
    #             })
    #
    #         temp['Summary_Financial_data'] = [{
    #             'source': 'Michael Watson Secretory of state',
    #             'summary': {
    #                 'currency': 'USD',
    #                 'income_statement': tempList[0]
    #             }
    #         }]
    #     # print(temp)
    #     return temp
