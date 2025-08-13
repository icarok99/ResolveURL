# -*- coding: utf-8 -*-
"""
EmbedPlayer resolver para ResolveURL
Baseado no método do WarezCDN
"""

import json
import urllib.parse
from resolveurl.lib import helpers
from resolveurl import common
from resolveurl.resolver import ResolveUrl, ResolverError


class EmbedPlayerResolver(ResolveUrl):
    name = "EmbedPlayer"
    domains = ["embedplayer1.xyz"]
    pattern = r'https?://([\w\.-]+)/video/([A-Za-z0-9]+)'

    def __init__(self):
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
            "Gecko/20100101 Firefox/121.0"
        )

    def get_media_url(self, host, media_id):
        try:
            if media_id.startswith("m3/"):
                headers = {'User-Agent': self.user_agent}
                return f"https://{host}/{media_id}" + helpers.append_headers(headers)

            master_request_url = f'https://{host}/player/index.php?data={media_id}&do=getVideo'
            origin_url = f'https://{host}/'

            headers = {
                'User-Agent': self.user_agent,
                'Origin': origin_url.rstrip('/'),
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://embed.embedplayer.site/'
            }

            response = self.net.http_POST(
                master_request_url,
                form_data={'hash': media_id, 'r': ''},
                headers=headers
            ).content

            data_json = json.loads(response)

            if 'securedLink' in data_json and data_json['securedLink']:
                headers.pop('X-Requested-With', None)
                return data_json['securedLink'] + helpers.append_headers(headers)

            if 'videoSource' in data_json and data_json['videoSource']:
                master_m3u8_url = data_json['videoSource']
                playlist = self.net.http_GET(
                    master_m3u8_url,
                    headers={
                        'Referer': 'https://embed.embedplayer.site/',
                        'User-Agent': self.user_agent
                    }
                ).content

                base_url = master_m3u8_url.rsplit("/", 1)[0] + "/"
                for line in playlist.split('\n'):
                    if line.strip():
                        if not line.startswith("http"):
                            line = base_url + line
                        line = urllib.parse.quote(line, safe=':/?&=%')
                        return line + helpers.append_headers({'User-Agent': self.user_agent})

            common.log_utils.log(f"[EmbedPlayer] JSON recebido sem link válido: {data_json}",
                                 level=common.log_utils.LOGDEBUG)
            raise ResolverError("Não foi possível encontrar o link de vídeo no JSON.")

        except Exception as e:
            raise ResolverError(f"Erro no resolver EmbedPlayer: {e}")

    def get_url(self, host, media_id):
        return f"https://{host}/video/{media_id}"
