"""
    Plugin for ResolveURL
    Copyright (C) 2023 gujal

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import re
from resolveurl.lib import helpers
from resolveurl.resolver import ResolveUrl, ResolverError
from resolveurl import common


class SecVideoResolver(ResolveUrl):
    name = 'SecVideo'
    domains = ['secvideo1.online', 'www.secvideo1.online', 'csst.online', 'www.csst.online']
    pattern = r'(?://|\.)(?:www\.)?((?:secvideo1|csst)\.online)/(?:videos|embed)/([A-Za-z0-9\-_]+)/?'

    def get_media_url(self, host, media_id):
        print(f"[SecVideoResolver] get_media_url chamado: host={host}, media_id={media_id}")
        web_url = self.get_url(host, media_id)
        print(f"[SecVideoResolver] URL embed: {web_url}")

        headers = {'User-Agent': common.FF_USER_AGENT}
        html = self.net.http_GET(web_url, headers=headers).content
        if isinstance(html, bytes):
            html = html.decode('utf-8', 'ignore')

        print(f"[SecVideoResolver] HTML recebido - tamanho: {len(html)} bytes")

        m = re.search(r'Playerjs.+?file\s*:\s*["\']([^"\']+)["\']', html, re.DOTALL | re.IGNORECASE)
        if not m:
            m = re.search(r'file\s*:\s*["\']([^"\']+)["\']', html, re.DOTALL | re.IGNORECASE)
        if not m:
            m2 = re.search(r'sources\s*:\s*(\[[^\]]+\])', html, re.DOTALL | re.IGNORECASE)
            if m2:
                src_block = m2.group(1)
                urls = re.findall(r'["\'](https?://[^"\']+)["\']', src_block)
                if urls:
                    print(f"[SecVideoResolver] Encontrou sources via 'sources': {urls}")
                    return urls[0] + helpers.append_headers(headers)
            raise ResolverError('No playable video found.')

        srcs_str = m.group(1).strip()
        print(f"[SecVideoResolver] String bruta de sources: {srcs_str}")

        # parser tolerante
        def parse_sources_from_string(s):
            sources = []
            if not s:
                return sources
            s = s.strip().strip('"').strip("'")
            # caso tenha formato [label]url
            items = s.split(',')
            for x in items:
                x = x.strip()
                if not x:
                    continue
                if ']' in x:
                    parts = x.split(']', 1)
                    label = parts[0].lstrip('[').strip()
                    url = parts[1].strip().rstrip('/')
                    if url.startswith('//'):
                        url = 'https:' + url
                    sources.append((label, url))
                else:
                    url = x.strip().rstrip('/')
                    if url.startswith('//'):
                        url = 'https:' + url
                    sources.append(('', url))
            return sources

        srcs = parse_sources_from_string(srcs_str)
        print(f"[SecVideoResolver] Fontes parseadas: {srcs}")

        if not srcs:
            raise ResolverError('No playable video found (parsed zero sources).')

        # normalizar e escolher melhor
        normalized = []
        for lab, url in srcs:
            lab = (lab or '').strip()
            m_lab = re.search(r'(\d{2,4})', lab)
            if m_lab:
                lab = m_lab.group(1)
            normalized.append((lab, url))

        print(f"[SecVideoResolver] Fontes normalizadas: {normalized}")

        try:
            chosen = helpers.pick_source(helpers.sort_sources_list(normalized))
            if isinstance(chosen, (list, tuple)):
                chosen_url = chosen[1] if len(chosen) > 1 else chosen[0]
            else:
                chosen_url = chosen
            print(f"[SecVideoResolver] URL escolhida: {chosen_url}")
            return chosen_url + helpers.append_headers(headers)
        except Exception as e:
            print(f"[SecVideoResolver] Falha no pick_source: {e}")
            return normalized[0][1] + helpers.append_headers(headers)

    def get_url(self, host, media_id):
        return self._default_get_url(host, media_id, template='https://{host}/embed/{media_id}/')
