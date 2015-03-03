#!/usr/bin/env python3

"""
    Copyright (c) 2014, Luis González Fernández - luisgf@luisgf.es
    Copyright (c) 2014, Jesús Cea Avión - jcea@jcea.es

    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
    this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
    ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
    LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
    CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
    INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
    CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
    ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
    POSSIBILITY OF SUCH DAMAGE.
"""

import argparse
import sys, os, os.path, time

from .logs import Logger
from .keys import KeyType, detect_key_type
from .signer import SignerFactory
from .errors import LibOpenBadgesException, SignerExceptions
from .confparser import ConfParser
from .mail import BadgeMail
from .util import __version__

# Entry Point
def main():
    global log
    parser = argparse.ArgumentParser(description='Badge Signer Parameters')
    parser.add_argument('-c', '--config', default='config.ini', help='Specify the config.ini file to use')
    parser.add_argument('-b', '--badge', required=True, help='Specify the badge name for sign')
    parser.add_argument('-r', '--receptor', required=True, help='Specify the receptor email of the badge')
    parser.add_argument('-o', '--output', default=os.path.curdir, help='Specify the output directory to save the badge.')
    parser.add_argument('-M', '--mail-badge', action='store_true', help='Send Badge to user mail')
    parser.add_argument('-e', '--evidence', help='Set an URL to the user evidence')
    parser.add_argument('-E', '--no-evidence', action='store_true', help='Do not use evidence')
    parser.add_argument('-x', '--expires', type=int, help='Set badge expiration after x days.')
    parser.add_argument('-d', '--debug', action='store_true', help='Show debug messages in runtime.')
    parser.add_argument('-v', '--version', action='version', version=__version__ )
    args = parser.parse_args()

    if bool(args.no_evidence) != (args.evidence is None) :  # XOR
        sys.exit("Please, choose '-e' OR '-E'")

    evidence = args.evidence  # If no evidence, evidence=None

    if args.expires:
        expiration = int(time.time()) + args.expires*86400
    else:
        expiration = None

    if args.badge:
        cf = ConfParser(args.config)
        conf = cf.read_conf()

        badge = 'badge_' + args.badge

        if not conf:
            print('ERROR: The config file %s NOT exists or is empty' % args.config)
            sys.exit(-1)

        if not conf[badge]:
            print('ERROR: %s is not defined in this config file' % args.badge)
            sys.exit(-1)

        log = Logger(base_log=conf['paths']['base_log'],
                      general=conf['logs']['general'],
                      signer=conf['logs']['signer'])

        try:
            badge_path = os.path.join(conf['paths']['base_image'],
                    conf[badge]['local_image'])
            priv_key = conf[badge]['private_key']

            if not os.path.isfile(badge_path):
                log.console.error('Badge file %s NOT exists.' % badge_path)
                sys.exit(-1)

            """ Reading the SVG content """
            with open(badge_path,"rb") as f:
                badge_image_data = f.read()

            """ Reading the keys """
            with open(priv_key,"rb") as f:
                priv_key_pem = f.read()

            key_type = detect_key_type(priv_key_pem)

            sf = SignerFactory(key_type=key_type, sign_key=priv_key_pem,
                               badge_name=badge,
                               image_url = conf[badge]['image'],
                               json_url=conf[badge]['badge'],
                               verify_key=conf[badge]['verify_key'],
                               identity=args.receptor, evidence=evidence,
                               expires=expiration)

            badge_file_out = sf.generate_output_filename(badge_path, args.output)
            badge_assertion = sf.generate_openbadge_assertion()

            if os.path.isfile(badge_file_out):
                log.console.warning('A %s OpenBadge has already signed for %s in %s' % (args.badge, args.receptor, badge_file_out))
                sys.exit(-1)

            log.console.info("Generating signature for badge '%s'..." % args.badge)
            badge_svg_out = sf.sign_svg(badge_image_data, badge_assertion)

            with open(badge_file_out, "wb") as f:
                f.write(badge_svg_out.encode('utf-8'))

            print('%s SIGNED for %s UID %s at %s' % (badge, args.receptor,
                                                   sf.get_uid(), badge_file_out))

            if bool(args.mail_badge):
                server = conf['smtp']['smtp_server']
                port = conf['smtp']['smtp_port']
                use_ssl = conf['smtp']['use_ssl']
                mail_from = conf['smtp']['mail_from']

                mail = BadgeMail(server, port, use_ssl, mail_from)
                subject, body = mail.get_mail_content(conf[badge]['mail'])
                mail.send(args.receptor, subject, body, [badge_file_out])

        except SignerExceptions:
            raise
        except LibOpenBadgesException:
            raise

if __name__ == '__main__':
    main()

