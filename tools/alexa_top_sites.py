#!/usr/bin/env python
import argparse
import requests
import re
import sys

# insert the result page number you want; first page is 0
ALEXA_GLOBAL_URL = 'http://www.alexa.com/topsites/global;%d'
ALEXA_COUNTRY_URL = 'http://www.alexa.com/topsites/countries;%d/%s'

COUNTRIES = [
    (('afghanistan','af'), 'AF'),
    (('albania','al'), 'AL'),
    (('algeria','dz'), 'DZ'),
    (('argentina','ar'), 'AR'),
    (('armenia','am'), 'AM'),
    (('australia','au'), 'AU'),
    (('austria','at'), 'AT'),
    (('azerbaijan','az'), 'AZ'),
    (('bahamas','bs'), 'BS'),
    (('bahrain','bh'), 'BH'),
    (('bangladesh','bd'), 'BD'),
    (('belarus','by'), 'BY'),
    (('belgium','be'), 'BE'),
    (('bolivia','bo'), 'BO'),
    (('bosniaandherzegovina','ba'), 'BA'),
    (('brazil','br'), 'BR'),
    (('bulgaria','bg'), 'BG'),
    (('cambodia','kh'), 'KH'),
    (('canada','ca'), 'CA'),
    (('chile','cl'), 'CL'),
    (('china','cn'), 'CN'),
    (('colombia','co'), 'CO'),
    (('costarica','cr'), 'CR'),
    (('croatia','hr'), 'HR'),
    (('cyprus','cy'), 'CY'),
    (('czechrepublic','cz'), 'CZ'),
    (('denmark','dk'), 'DK'),
    (('dominicanrepublic','do'), 'DO'),
    (('ecuador','ec'), 'EC'),
    (('egypt','eg'), 'EG'),
    (('elsalvador','sv'), 'SV'),
    (('estonia','ee'), 'EE'),
    (('finland','fi'), 'FI'),
    (('france','fr'), 'FR'),
    (('georgia','ge'), 'GE'),
    (('germany','de'), 'DE'),
    (('ghana','gh'), 'GH'),
    (('greece','gr'), 'GR'),
    (('guatemala','gt'), 'GT'),
    (('honduras','hn'), 'HN'),
    (('hongkong','hk'), 'HK'),
    (('hungary','hu'), 'HU'),
    (('iceland','is'), 'IS'),
    (('india','in'), 'IN'),
    (('indonesia','id'), 'ID'),
    (('iran','ir'), 'IR'),
    (('iraq','iq'), 'IQ'),
    (('ireland','ie'), 'IE'),
    (('israel','il'), 'IL'),
    (('italy','it'), 'IT'),
    (('jamaica','jm'), 'JM'),
    (('japan','jp'), 'JP'),
    (('jordan','jo'), 'JO'),
    (('kazakhstan','kz'), 'KZ'),
    (('kenya','ke'), 'KE'),
    (('kuwait','kw'), 'KW'),
    (('kyrgyzstan','kg'), 'KG'),
    (('latvia','lv'), 'LV'),
    (('lebanon','lb'), 'LB'),
    (('libya','ly'), 'LY'),
    (('lithuania','lt'), 'LT'),
    (('luxembourg','lu'), 'LU'),
    (('macedonia','mk'), 'MK'),
    (('madagascar','mg'), 'MG'),
    (('malaysia','my'), 'MY'),
    (('malta','mt'), 'MT'),
    (('mauritania','mr'), 'MR'),
    (('mauritius','mu'), 'MU'),
    (('mexico','mx'), 'MX'),
    (('moldova','md'), 'MD'),
    (('mongolia','mn'), 'MN'),
    (('montenegro','me'), 'ME'),
    (('morocco','ma'), 'MA'),
    (('nepal','np'), 'NP'),
    (('netherlands','nl'), 'NL'),
    (('newzealand','nz'), 'NZ'),
    (('nicaragua','ni'), 'NI'),
    (('nigeria','ng'), 'NG'),
    (('norway','no'), 'NO'),
    (('oman','om'), 'OM'),
    (('pakistan','pk'), 'PK'),
    (('palestinianterritory','ps'), 'PS'),
    (('panama','pa'), 'PA'),
    (('paraguay','py'), 'PY'),
    (('peru','pe'), 'PE'),
    (('philippines','ph'), 'PH'),
    (('poland','pl'), 'PL'),
    (('portugal','pt'), 'PT'),
    (('puertorico','pr'), 'PR'),
    (('qatar','qa'), 'QA'),
    (('reunion','re'), 'RE'),
    (('romania','ro'), 'RO'),
    (('russia','ru'), 'RU'),
    (('saudiarabia','sa'), 'SA'),
    (('senegal','sn'), 'SN'),
    (('serbia','rs'), 'RS'),
    (('singapore','sg'), 'SG'),
    (('slovakia','sk'), 'SK'),
    (('slovenia','si'), 'SI'),
    (('southafrica','za'), 'ZA'),
    (('southkorea','kr'), 'KR'),
    (('spain','es'), 'ES'),
    (('srilanka','lk'), 'LK'),
    (('sudan','sd'), 'SD'),
    (('sweden','se'), 'SE'),
    (('switzerland','ch'), 'CH'),
    (('syrianarabrepublic','sy'), 'SY'),
    (('taiwan','tw'), 'TW'),
    (('tanzania','tz'), 'TZ'),
    (('thailand','th'), 'TH'),
    (('trinidadandtobago','tt'), 'TT'),
    (('tunisia','tn'), 'TN'),
    (('turkey','tr'), 'TR'),
    (('uganda','ug'), 'UG'),
    (('ukraine','ua'), 'UA'),
    (('unitedarabemirates','ae'), 'AE'),
    (('unitedkingdom', 'greatbritain', 'uk','gb'), 'GB'),
    (('unitedstates', 'usa','us'), 'US'),
    (('uruguay','uy'), 'UY'),
    (('uzbekistan','uz'), 'UZ'),
    (('venezuela','ve'), 'VE'),
    (('vietnam','vn'), 'VN'),
    (('yemen','ye'), 'YE'),
    ]


def main():
    sitelist = []

    page = 0
    while len(sitelist) < args.numsites:

        if args.country:
            r = requests.get(ALEXA_COUNTRY_URL % (page, args.country))
        else:
            r = requests.get(ALEXA_GLOBAL_URL % page)
            
        for match in re.finditer(r'<a href="/siteinfo/(+*)">', r.text):
            sitelist.append(match.group(1))
        page += 1

    for site in sitelist[:args.numsites]:
        print 'http://%s' % site

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Downloads a list of top sites from Alexa.')
    parser.add_argument('-n', '--numsites', default=100, help='Number of top sites to retrieve')
    parser.add_argument('-c', '--country', help='Restrict results to top sites for specified country. Default is global.')
    args = parser.parse_args()

    args.numsites = int(args.numsites)

    if args.country:
        found = False
        for names, code in COUNTRIES:
            if args.country.lower().replace(' ','') in names:
                args.country = code
                found = True
                break
        if not found:
            print 'Unrecognized country: %s' % args.country
            sys.exit(-1)

    main()
