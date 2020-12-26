#!/usr/bin/env python3.6
import requests
from akamai.edgegrid import EdgeGridAuth, EdgeRc
import json
import re
import sys
import os
from datetime import datetime,timedelta
from time import strftime
import time
from urllib.parse import urlencode
import texttable as tt
import pandas
from pandas import ExcelWriter
import http.client
import urllib3
from urllib.parse import urlparse, parse_qs,urljoin
from akamaiproperty import AkamaiProperty
import pydig
from edgehostname import getEdgeHostNameInfo
from config_parser import parseConfig
from basepageparse import getBasePageUrl
import getpass

username = getpass.getuser()
edgercpath = os.path.join("/root",".edgerc")
edgerc = EdgeRc(edgercpath)
section = 'default'
baseurl = 'https://%s' % edgerc.get(section, 'host')
s = requests.Session()
s.auth = EdgeGridAuth.from_edgerc(edgerc, section)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

http.client._MAXHEADERS = 1000
pandas.options.display.float_format = "{:,.2f}".format

headers = {'Content-Type': 'application/json'}


def getAccountSwitchKey(apiClientId,accountName):
    id= accountName
    # Request switchkey for the Account name
    switchkey = s.get(baseurl + "/identity-management/v1/open-identities/{}/account-switch-keys?search={}".format(apiClientId,id))
    # get the json in dictionary
    switchkey = json.loads(switchkey.text)
    # search for account switch key in the List and assign it to variable skey
    if 'accountSwitchKey' in switchkey[0]:
        skey = (switchkey[0]['accountSwitchKey'])
        return skey
    else:
        return 0

def getAvailableFeatures(propertyId,version,accountSwitchKey):
    behaviorList = []
    params =    {
                    'accountSwitchKey': accountSwitchKey
                }

    path = "/papi/v1/properties/{propertyId}/versions/{propertyVersion}/available-behaviors".format(propertyId=propertyId,propertyVersion=version)
    fullurl = urljoin(baseurl, path)
    result = s.get(fullurl, headers=headers,params=params)
    code = result.status_code
    body = result.json()
    for behaviors in body["behaviors"]["items"]:
        behaviorList.append(behaviors["name"])
    return behaviorList

def listDiff(li1, li2):
    return (list(list(set(li1)-set(li2)) + list(set(li2)-set(li1))))

def getGeneralInfo(writer,config,hostname,accountSwitchKey):
    print("General Info of {} and {} writing to excel......".format(config,hostname))
    myProperty = AkamaiProperty(edgercpath,config,accountSwitchKey)
    data = {}
    data["HostName"] = hostname
    data["Config"] = config
    data["Contract"] = myProperty.contractId
    data["Group"] = myProperty.groupId
    data["Active Staging Version"] = myProperty.getStagingVersion()
    data["Active Production Version"] = myProperty.getProductionVersion()

    google_resolver = pydig.Resolver(executable='/usr/bin/dig',nameservers=['8.8.8.8'])
    ipv4_chain = google_resolver.query(hostname, 'A')
    ipv6_chain = google_resolver.query(hostname, 'AAAA')
    data["IPV4 Chain"] = ipv4_chain
    data["IPV6 Chain"] = ipv6_chain
    if 'akamai' in ipv4_chain[0]:
        ehn = getEdgeHostNameInfo(hostname)
    else:
        ehn = getEdgeHostNameInfo(ipv4_chain[0])
    data["Product"] = ehn['Product']
    data["Network"] = ehn['Network']
    if 'Serial' in ehn:
        data["Serial"] = ehn['Serial']
    else:
        data["Slot"] = ehn['Slot']
    data['DualStack'] = ehn['DualStack']

    availableBehaviorList =  getAvailableFeatures(myProperty.propertyId,myProperty.getProductionVersion(),accountSwitchKey)
    data['Available Behaviors'] = availableBehaviorList

    behaviorParsedList = parseConfig(edgercpath,accountSwitchKey,config,myProperty.getProductionVersion())
    usedbehaviorList = []

    for behavior in behaviorParsedList:
        usedbehaviorList.append(behavior["behavior"]["name"])
    usedbehaviorList = list(dict.fromkeys(usedbehaviorList))


    data['Used Behaviors'] = usedbehaviorList
    data['Unused Behaviors'] = listDiff(availableBehaviorList,usedbehaviorList)

    #print(data)

    df=pandas.json_normalize(data)
    result = df.transpose()
    result.to_excel(writer, sheet_name='General',index = True)
    return data["Network"]


def getStartDay(interval):
    start_day = 0
    if interval == 1:
        start_day = 29
    elif interval == 2:
        start_day = 59
    elif interval == 3:
        start_day = 89

    return start_day

def getTrafficbyResponseClass(writer,cp_code,interval,accountSwitchKey):
    #get property details
    data = {}
    data['objectIds'] = cp_code
    data['metrics'] = ['edgeHits','edgeHitsPercent','originHits','originHitsPercent']

    filters = {}
    filters['delivery_type'] = ['non_secure','secure']
    filters['ip_version'] = ['ipv4','ipv6']
    filters['response_class'] = ['5xx','4xx','3xx','2xx','1xx']
    filters['response_status'] = ['success','error']
    filters['traffic'] = ['get_head_responses','put_post_requests']

    #data['filters'] = filters
    json_data = json.dumps(data)

    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today()-timedelta(days=getStartDay(interval))).strftime('%Y-%m-%d')

    params =    {
                    'accountSwitchKey': accountSwitchKey,
                    'start':start,
                    'end':end
                }

    path = "/reporting-api/v1/reports/traffic-by-responseclass/versions/1/report-data"
    fullurl = urljoin(baseurl, path)
    result = s.post(fullurl, headers=headers, data = json_data, params=params)
    code = result.status_code
    body = result.json()


    if code == 200:
        print("Traffic by Response Class writing to excel......")
        df=pandas.json_normalize(body['data'])
        pandas.set_option('display.max_rows', df.shape[0]+1)

        df['response_class'] = df['response_class']
        df['edgeHitsPercent'] = df['edgeHitsPercent'].astype(float)
        df['originHitsPercent'] = df['originHitsPercent'].astype(float)

        df.sort_values(by=['response_class'], inplace=True, ascending=True)
        df.to_excel(writer, sheet_name='Traffic_ResponseClass',index = False)
    else:
    	print ("Failed to retrieve configuration details.")
    	print ("Response Code: ",code)

def getTrafficbyResponseCode(writer,cp_code,interval,accountSwitchKey):
    #get property details
    data = {}
    data['objectIds'] = cp_code
    data['metrics'] = ['edgeHits','edgeHitsPercent','originHits','originHitsPercent']

    filters = {}
    filters['delivery_type'] = ['non_secure','secure']
    filters['ip_version'] = ['ipv4','ipv6']
    filters['response_class'] = ['5xx','4xx','3xx','2xx','1xx']
    filters['response_code'] = ["101","100",
                                "200","201","206","204","203",
                                "301","302","303","304","307",
                                "404","401","403",
                                "500","501","502","503","504"]
    filters['response_status'] = ['success','error']
    filters['traffic'] = ['get_head_responses','put_post_requests']

    #data['filters'] = filters
    json_data = json.dumps(data)


    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today()-timedelta(days=getStartDay(interval))).strftime('%Y-%m-%d')

    params =    {
                    'accountSwitchKey': accountSwitchKey,
                    'start':start,
                    'end':end
                }

    path = "/reporting-api/v1/reports/traffic-by-response/versions/1/report-data"
    fullurl = urljoin(baseurl, path)
    result = s.post(fullurl, headers=headers, data = json_data, params=params)
    code = result.status_code
    body = result.json()

    if code == 200:
        print("Traffic by Response Codes writing to excel......")
        df=pandas.json_normalize(body['data'])
        pandas.set_option('display.max_rows', df.shape[0]+1)

        df['response_code'] = df['response_code'].astype(int)
        df['edgeHits'] = df['edgeHits'].astype(int)
        df['originHits'] = df['originHits'].astype(int)
        df['edgeHitsPercent'] = df['edgeHitsPercent'].astype(float)
        df['originHitsPercent'] = df['originHitsPercent'].astype(float)

        df.sort_values(by=['response_code'], inplace=True, ascending=True)
        df.to_excel(writer, sheet_name='Traffic_ResponseCode',index = False)
    else:
    	print ("Failed to retrieve configuration details.")
    	print ("Response Code: ",code)

def getHitsbyOS(writer,cp_code,interval,accountSwitchKey):
    #get property details
    data = {}
    data['objectIds'] = cp_code
    data['metrics'] = ['successfulHits','successfulHitsPercent']
    json_data = json.dumps(data)


    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today()-timedelta(days=getStartDay(interval))).strftime('%Y-%m-%d')

    params =    {
                    'accountSwitchKey': accountSwitchKey,
                    'start':start,
                    'end':end
                }

    path = "/reporting-api/v1/reports/hits-by-os/versions/1/report-data"
    fullurl = urljoin(baseurl, path)
    result = s.post(fullurl, headers=headers, data = json_data, params=params)
    code = result.status_code
    body = result.json()

    if code == 200:
        print("Hits by OS writing to excel......")
        df=pandas.json_normalize(body['data'])
        pandas.set_option('display.max_rows', df.shape[0]+1)

        df.sort_values(by=['successfulHitsPercent'], inplace=True, ascending=False)
        df.to_excel(writer, sheet_name='HitsbyOs',index = False)
    else:
    	print ("Failed to retrieve configuration details.")
    	print ("Response Code: ",code)

def getDailyUniqueHitsbyCountry(writer,cp_code,interval,accountSwitchKey):
    #get property details
    data = {}
    data['objectIds'] = cp_code
    data['metrics'] = ['country','edgeHits']
    json_data = json.dumps(data)


    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today()-timedelta(days=getStartDay(interval))).strftime('%Y-%m-%d')

    params =    {
                    'accountSwitchKey': accountSwitchKey,
                    'start':start,
                    'end':end
                }

    path = "/reporting-api/v1/reports/enhancedtraffic-by-country/versions/1/report-data"
    fullurl = urljoin(baseurl, path)
    result = s.post(fullurl, headers=headers, data = json_data, params=params)
    code = result.status_code
    body = result.json()


    if code == 200:
        print("Traffic by Country writing to excel......")
        df=pandas.json_normalize(body['data'])
        pandas.set_option('display.max_rows', df.shape[0]+1)

        df['edgeHits'] = df['edgeHits'].astype(int)
        df.sort_values(by=['edgeHits'], inplace=True, ascending=False)
        df.head(10).to_excel(writer, sheet_name='HitsbyCountry',index = False)
    else:
    	print ("Failed to retrieve configuration details.")
    	print ("Response Code: ",code)

def getTopUrls(writer,hostname,cp_code,interval,accountSwitchKey):
    #get property details
    data = {}
    data['objectIds'] = cp_code
    data["objectType"]=  "cpcode"
    data['metrics'] = ["allEdgeHits", "allOriginHits", "allHitsOffload"]

    #filters = {}
    #filters['url_contain'] = ["origin-giftcards.landal.de"]
    #data['filters'] = filters

    json_data = json.dumps(data)

    end = datetime.today().replace(hour=0,minute=0,second=0,microsecond=0).isoformat()
    start = (datetime.today()-timedelta(days=getStartDay(interval))).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()


    params =    {
                    'accountSwitchKey': accountSwitchKey,
                    'start':start,
                    'end':end
                }

    path = "reporting-api/v1/reports/urlhits-by-url/versions/1/report-data"
    fullurl = urljoin(baseurl, path)
    result = s.post(fullurl, headers=headers, data = json_data, params=params)
    code = result.status_code
    body = result.json()


    if code == 200:
        print("Top Urls writing to excel......")
        df=pandas.json_normalize(body['data'])
        pandas.set_option('display.max_rows', df.shape[0]+1)

        df['allEdgeHits'] = df['allEdgeHits'].astype(int)
        df['allOriginHits'] = df['allOriginHits'].astype(int)

        df.sort_values(by=['allEdgeHits'], inplace=True, ascending=False)
        newdf = df.head(20)
        newdf.to_excel(writer, sheet_name='Top Urls',index = False)
    else:
    	print ("Failed to retrieve configuration details.")
    	print ("Response Code: ",code)

def getOffloadAnalysis(writer,hostname,cp_code,interval,accountSwitchKey):
    #get property details
    data = {}
    data['objectIds'] = cp_code
    data["objectType"]=  "cpcode"
    data['metrics'] = ["allEdgeBytes", "allOriginBytes", "allBytesOffload"]

    #filters = {}
    #filters['url_contain'] = ["origin-giftcards.landal.de"]
    #data['filters'] = filters

    json_data = json.dumps(data)

    end = datetime.today().replace(hour=0,minute=0,second=0,microsecond=0).isoformat()
    start = (datetime.today()-timedelta(days=getStartDay(interval))).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()

    params =    {
                    'accountSwitchKey': accountSwitchKey,
                    'start':start,
                    'end':end
                }

    path = "/reporting-api/v1/reports/urlbytes-by-url/versions/1/report-data"
    fullurl = urljoin(baseurl, path)
    result = s.post(fullurl, headers=headers, data = json_data, params=params)
    code = result.status_code
    body = result.json()


    if code == 200:
        print("Offload Details writing to excel......")
        df=pandas.json_normalize(body['data'])
        pandas.set_option('display.max_rows', df.shape[0]+1)

        df['allEdgeBytes'] = df['allEdgeBytes'].astype(int)/1000000000
        df['allOriginBytes'] = df['allOriginBytes'].astype(int)/1000000000
        df['extension'] = df["hostname.url"].apply(lambda x: os.path.splitext(os.path.basename(x))[1])
        df.to_excel(writer, sheet_name='OffloadAnalysis',index = False)
    else:
    	print ("Failed to retrieve configuration details.")
    	print ("Response Code: ",code)

def get4xxTopUrls(writer,hostname,cp_code,interval,accountSwitchKey):
    data = {}
    data['objectIds'] = cp_code
    data["objectType"]=  "cpcode"
    data['metrics'] = ["404EdgeHits","4XXOtherEdgeHits"]

    #filters = {}
    #filters['url_contain'] = ["origin-giftcards.landal.de"]
    #data['filters'] = filters

    json_data = json.dumps(data)

    end = datetime.today().replace(hour=0,minute=0,second=0,microsecond=0).isoformat()
    start = (datetime.today()-timedelta(days=getStartDay(interval))).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()


    params =    {
                    'accountSwitchKey': accountSwitchKey,
                    'start':start,
                    'end':end
                }

    path = "/reporting-api/v1/reports/url4XXresponses-by-url/versions/1/report-data"
    fullurl = urljoin(baseurl, path)
    result = s.post(fullurl, headers=headers, data = json_data, params=params)
    code = result.status_code
    body = result.json()

    if code == 200:
        print("Top 4xx Urls writing to excel......")
        df=pandas.json_normalize(body['data'])
        pandas.set_option('display.max_rows', df.shape[0]+1)

        df['404EdgeHits'] = df['404EdgeHits'].astype(int)
        df['4XXOtherEdgeHits'] = df['4XXOtherEdgeHits'].astype(int)

        df.sort_values(by=['404EdgeHits','4XXOtherEdgeHits'], inplace=True, ascending=False)
        newdf = df.head(20)

        newdf.to_excel(writer, sheet_name='4xx Urls',index = False)
    else:
    	print ("Failed to retrieve configuration details.")
    	print ("Response Code: ",code)

def get3xxTopUrls(writer,hostname,cp_code,interval,accountSwitchKey):
    data = {}
    data['objectIds'] = cp_code
    data["objectType"]=  "cpcode"
    data['metrics'] = ["302EdgeHits","304EdgeHits","3XXOtherEdgeHits"]

    #filters = {}
    #filters['url_contain'] = ["origin-giftcards.landal.de"]
    #data['filters'] = filters
    json_data = json.dumps(data)

    end = datetime.today().replace(hour=0,minute=0,second=0,microsecond=0).isoformat()
    start = (datetime.today()-timedelta(days=getStartDay(interval))).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()


    params =    {
                    'accountSwitchKey': accountSwitchKey,
                    'start':start,
                    'end':end
                }

    path = "/reporting-api/v1/reports/url3XXresponses-by-url/versions/1/report-data"
    fullurl = urljoin(baseurl, path)
    result = s.post(fullurl, headers=headers, data = json_data, params=params)
    code = result.status_code
    body = result.json()

    if code == 200:
        print("Top 3xx Urls writing to excel......")
        df=pandas.json_normalize(body['data'])
        pandas.set_option('display.max_rows', df.shape[0]+1)

        df['302EdgeHits'] = df['302EdgeHits'].astype(int)
        df['304EdgeHits'] = df['304EdgeHits'].astype(int)

        df.sort_values(by=['302EdgeHits','304EdgeHits'], inplace=True, ascending=False)
        newdf = df.head(20)

        newdf.to_excel(writer, sheet_name='3xx Urls',index = False)
    else:
    	print ("Failed to retrieve configuration details.")
    	print ("Response Code: ",code)

def get2xxTopUrls(writer,hostname,cp_code,interval,accountSwitchKey):
    data = {}
    data['objectIds'] = cp_code
    data["objectType"]=  "cpcode"
    data['metrics'] = ["200EdgeHits","206EdgeHits","2XXOtherEdgeHits"]

    #filters = {}
    #filters['url_contain'] = ["origin-giftcards.landal.de"]
    #data['filters'] = filters

    json_data = json.dumps(data)

    end = datetime.today().replace(hour=0,minute=0,second=0,microsecond=0).isoformat()
    start = (datetime.today()-timedelta(days=getStartDay(interval))).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()


    params =    {
                    'accountSwitchKey': accountSwitchKey,
                    'start':start,
                    'end':end
                }

    path = "/reporting-api/v1/reports/url2XXresponses-by-url/versions/1/report-data"
    fullurl = urljoin(baseurl, path)
    result = s.post(fullurl, headers=headers, data = json_data, params=params)
    code = result.status_code
    body = result.json()

    if code == 200:
        print("Top 2xx Urls writing to excel......")
        df=pandas.json_normalize(body['data'])
        pandas.set_option('display.max_rows', df.shape[0]+1)

        df['200EdgeHits'] = df['200EdgeHits'].astype(int)
        df['206EdgeHits'] = df['206EdgeHits'].astype(int)

        df.sort_values(by=['200EdgeHits','206EdgeHits'], inplace=True, ascending=False)
        newdf = df.head(20)

        newdf.to_excel(writer, sheet_name='2xx Urls',index = False)
    else:
    	print ("Failed to retrieve configuration details.")
    	print ("Response Code: ",code)

def getOffloadAnalysisPage(writer,cp_code,network,hostname):
    print("Offload Details of Base Page writing to excel......")
    if network == 'Enhanced TLS':
        fullpath = 'https://'+hostname
    else:
        fullpath = 'http://'+hostname
    allurlList = getBasePageUrl(fullpath)
    df = pandas.DataFrame(allurlList,columns =['url'])
    filtered_df = df[df['url'].str.contains(fullpath)]
    filtered_df["CacheControl"] = ""
    filtered_df["Expires"] = ""
    filtered_df['Akamai Caching'] = ""
    #print(filtered_df)

    pragma_headers = {'Pragma':'akamai-x-get-client-ip, akamai-x-cache-on, akamai-x-cache-remote-on, akamai-x-check-cacheable, akamai-x-get-cache-key, akamai-x-get-extracted-values, akamai-x-get-nonces, akamai-x-get-ssl-client-session-id, akamai-x-get-true-cache-key, akamai-x-serial-no, akamai-x-feo-trace, akamai-x-get-request-id, x-akamai-a2-trace,x-akamai-rua-debug,x-akamai-a2-enable, x-akamai-cpi-trace, akamai-x-get-brotli-status'}
    for ind in filtered_df.index:
        prod_response = requests.get(df['url'][ind],headers=pragma_headers,verify=False)
        #print('URL:',df['url'][ind])
        for temp in prod_response.headers:
            if temp == 'X-Cache-Key':
                filtered_df['Akamai Caching'][ind] = prod_response.headers[temp].split('/')[4]
            elif temp == 'Cache-Control':
                filtered_df['CacheControl'][ind] = prod_response.headers[temp]
            elif temp == 'Expires':
                filtered_df[temp][ind] = prod_response.headers[temp]
    filtered_df.to_excel(writer, sheet_name='Base Page Analysis',index = False)


def main():
    filename = 'data.json'
    file = open (filename, "r")
    data = json.loads(file.read())

    apiClientId = data[0]["apiClientId"]

    parentDirectory = os.getcwd()
    directory = "osreports"
    newpath = os.path.join(parentDirectory, directory)
    #os.mkdir(newpath)

    for items in data[1:]:
        hostname = items["hostname"]
        cp_code = items["cpcode"]
        interval = items["interval"]
        config = items["config"]
        accountSwitchKey = getAccountSwitchKey(apiClientId,items["accountName"])
        if accountSwitchKey == 0:
            print("Cant Find the SwitchKey for ",items["accountName"])
            continue

        file_name = str(cp_code) + '.xlsx'
        full_file_name = os.path.join(newpath,file_name)

        writer = pandas.ExcelWriter(full_file_name, engine='xlsxwriter')

        network = getGeneralInfo(writer,config,hostname,accountSwitchKey)
        getTrafficbyResponseCode(writer,cp_code,int(interval),accountSwitchKey)
        getTrafficbyResponseClass(writer,cp_code,int(interval),accountSwitchKey)

        getTopUrls(writer,hostname,cp_code,int(interval),accountSwitchKey)
        get4xxTopUrls(writer,hostname,cp_code,int(interval),accountSwitchKey)
        get3xxTopUrls(writer,hostname,cp_code,int(interval),accountSwitchKey)
        get2xxTopUrls(writer,hostname,cp_code,int(interval),accountSwitchKey)

        getHitsbyOS(writer,cp_code,int(interval),accountSwitchKey)
        getDailyUniqueHitsbyCountry(writer,cp_code,int(interval),accountSwitchKey)
        getOffloadAnalysis(writer,hostname,cp_code,int(interval),accountSwitchKey)

        getOffloadAnalysisPage(writer,cp_code,network,hostname)
        writer.save()

if __name__ == '__main__':
    main()
