# -*- coding: utf-8 -*-
"""
WarezCDN resolver para ResolveURL
Compatível com ResolveURL oficial (usa self.net)
Suporte para securedLink, master.txt e caminhos relativos
"""

import json
import urllib.parse
from resolveurl.lib import helpers
from resolveurl import common
from resolveurl.resolver import ResolveUrl, ResolverError


class WarezCDNResolver(ResolveUrl):
    name = "WarezCDN"
    domains = ["warezcdn.link", "basseqwevewcewcewecwcw.xyz"]
    pattern = r'https?://([\w\.-]+)/video/([A-Za-z0-9]+)'

    def __init__(self):
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
            "Gecko/20100101 Firefox/121.0"
        )

    def get_media_url(self, host, media_id):
        try:
            # Caso já seja link final /m3/
            if host.endswith(".xyz") and media_id.startswith("m3/"):
                headers = {'User-Agent': self.user_agent}
                return f"https://{host}/{media_id}" + helpers.append_headers(headers)

            # URL do player
            master_request_url = f'https://{host}/player/index.php?data={media_id}&do=getVideo'

            origin_url = f'https://{host}/'
            headers = {
                'User-Agent': self.user_agent,
                'Origin': origin_url.rstrip('/'),
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://embed.warezcdn.link/'
            }

            response = self.net.http_POST(
                master_request_url,
                form_data={'hash': media_id, 'r': ''},
                headers=headers
            ).content

            data_json = json.loads(response)

            # Primeiro tenta securedLink (link direto)
            if 'securedLink' in data_json and data_json['securedLink']:
                headers.pop('X-Requested-With', None)
                return data_json['securedLink'] + helpers.append_headers(headers)

            # Se não tiver securedLink, tenta videoSource (playlist)
            if 'videoSource' in data_json and data_json['videoSource']:
                master_m3u8_url = data_json['videoSource']
                playlist = self.net.http_GET(
                    master_m3u8_url,
                    headers={
                        'Referer': 'https://embed.warezcdn.link/',
                        'User-Agent': self.user_agent
                    }
                ).content

                base_url = master_m3u8_url.rsplit("/", 1)[0] + "/"
                for line in playlist.split('\n'):
                    if line.strip():  # ignora linhas vazias
                        if not line.startswith("http"):
                            line = base_url + line
                        line = urllib.parse.quote(line, safe=':/?&=%')
                        return line + helpers.append_headers({'User-Agent': self.user_agent})

            # Se não encontrou nada, loga para debug
            common.log_utils.log(f"[WarezCDN] JSON recebido sem link válido: {data_json}", level=common.log_utils.LOGDEBUG)
            raise ResolverError("Não foi possível encontrar o link de vídeo no JSON.")

        except Exception as e:
            raise ResolverError(f"Erro no resolver WarezCDN: {e}")

    def get_url(self, host, media_id):
        return f"https://{host}/video/{media_id}"
