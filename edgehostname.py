#https://collaborate.akamai.com/confluence/display/GPO/Web+Exp+Products+and+Maprules

import pydig
akamai_level1hostnames = ['edgesuite','edgekey','edgesuite-staging','edgekey-staging','akamaized','akamaized-staging']
akamai_leve2hostnames = ['akamai','akamaiedge']

product_prefix = {}
product_prefix['q'] = 'Alta_u'
product_prefix['x'] = 'Alta_s'
product_prefix['f1'] = 'Ion Media Advanced_u'
product_prefix['j'] = 'Ion Media Advanced_s'
product_prefix['r'] = 'Ion_u'
product_prefix['a'] = 'Ion_s'
product_prefix['b'] = 'Dynamic Site Accelerator'
product_prefix['w7'] = 'Rich Media Accelerator_u'
product_prefix['i'] = 'Rich Media Accelerator_s'
product_prefix['g1'] = 'Dynamic Site Delivery_u'
product_prefix['f'] = 'Dynamic Site Delivery_s'



def getEdgeHostNameInfo(edgehostname):
    hostname_detail = {}
    hostname_detail['Network'] = 'Enhanced TLS'
    hostname_detail['DualStack'] = 'No'
    hostname_detail['HTTPS'] = 'No'

    scname = pydig.query(edgehostname, 'CNAME')
    scname_list = scname[0].split('.')
    map = '.'.join(scname_list)
    if scname_list:
        if len(scname_list[1]) > 3:
            if scname_list[1][:3] == 'dsc':
                hostname_detail['DualStack'] = 'Yes'
                hostname_detail['Product'] = product_prefix[scname_list[1][3:]]
        else:
            hostname_detail['Product'] = product_prefix[scname_list[1]]
        if scname_list[2] == 'akamaiedge':
            hostname_detail['HTTPS'] = 'Yes'
        if scname_list[0][0] == 'a':
            hostname_detail['Network'] = 'Standard TLS'
            hostname_detail['Serial'] =  scname_list[0][1:]
        else:
            hostname_detail['Slot'] =  scname_list[0][1:]


    else:
        print("No Cname for the hostname")

    return hostname_detail
