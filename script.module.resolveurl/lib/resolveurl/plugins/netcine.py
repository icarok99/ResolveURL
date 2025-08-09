# -*- coding: utf-8 -*-
from resolveurl.lib import helpers
from resolveurl import common
from resolveurl.resolver import ResolveUrl, ResolverError
import re

try:
    from urllib.parse import urlparse
except Exception:
    from urlparse import urlparse


class NetcineResolver(ResolveUrl):
    name = 'netcine'
    domains = [
        'netcine.lat', 'netcinehd.lat', 'booo.lat',
        'netcine.com', 'netcine.net', 'netcine.org'
    ]
    # IMPORTANTE: agora temos 2 grupos de captura -> (host) / (media_id)
    pattern = r'(?://|\.)(netcine\.lat|netcinehd\.lat|booo\.lat|netcine\.com|netcine\.net|netcine\.org)/(.+)'

    def __init__(self):
        self.net = common.Net()

    def get_url(self, host, media_id):
        """
        Se media_id já for uma URL completa, retorne-a.
        Se media_id for um path (ex: 'media-player/arquivo.php?...'), monte a URL absoluta.
        Caso contrário, mantenha comportamento de embed fallback.
        """
        # media_id pode vir com querystring; se já for URL absoluta:
        if media_id.startswith('http://') or media_id.startswith('https://'):
            return media_id

        # se veio como path absoluto (começa com '/'), monta com host
        if media_id.startswith('/'):
            return 'https://{0}{1}'.format(host, media_id)

        # se parece com "media-player/..." (sem leading slash), também monta
        if '/' in media_id or '?' in media_id or '=' in media_id:
            return 'https://{0}/{1}'.format(host, media_id)

        # fallback: tenta montar embed-<id> (compatibilidade com alguns padrões)
        return 'https://{host}/embed-{media_id}.html'.format(host=host, media_id=media_id)

    def get_media_url(self, host, media_id):
        web_url = self.get_url(host, media_id)
        print('[netcine] start get_media_url ->', web_url)
        if not web_url:
            print('[netcine] URL inválida')
            raise ResolverError('URL inválida')

        headers = {'User-Agent': common.FF_USER_AGENT}
        try:
            p = urlparse(web_url)
            headers['Referer'] = '{0}://{1}/'.format(p.scheme, p.netloc)
        except Exception:
            headers['Referer'] = web_url
        headers['Cookie'] = 'XCRF%3DXCRF'

        print('[netcine] headers ->', headers)

        try:
            html = self.net.http_GET(web_url, headers=headers).content
            print('[netcine] página inicial obtida, tamanho:', len(html) if html else 0)
            print('[netcine] snippet:', (html[:200] + '...') if html and len(html) > 200 else html)
        except Exception as e:
            print('[netcine] falha ao obter a página:', repr(e))
            raise ResolverError('Falha ao obter a página')

        player_link = None
        m = re.search(r'<div[^>]*id=["\']content["\'][^>]*>.*?<a[^>]+href=["\']([^"\']+)["\']', html, re.DOTALL | re.IGNORECASE)
        if m:
            player_link = m.group(1)
            print('[netcine] player link encontrado (raw):', player_link)
            if player_link.startswith('/'):
                try:
                    p = urlparse(web_url)
                    player_link = p.scheme + '://' + p.netloc + player_link
                    print('[netcine] player link convertido para absoluto:', player_link)
                except Exception:
                    print('[netcine] falha ao construir player_link absoluto')
        else:
            print('[netcine] nenhum player link dentro de <div id="content"> encontrado')

        if not player_link:
            player_link = web_url
            print('[netcine] usando web_url como player_link fallback:', player_link)

        try:
            player_html = self.net.http_GET(player_link, headers=headers).content
            print('[netcine] player HTML obtido, tamanho:', len(player_html) if player_html else 0)
            print('[netcine] player snippet:', (player_html[:200] + '...') if player_html and len(player_html) > 200 else player_html)
        except Exception as e:
            print('[netcine] falha ao obter o player:', repr(e))
            raise ResolverError('Falha ao obter o player')

        # 1) base64 inline
        try:
            b64 = re.search(r'base64,([^"\']+)', player_html)
            if b64:
                print('[netcine] base64 inline encontrado')
                decoded = helpers.b64decode(b64.group(1))
                print('[netcine] base64 decodificado, tamanho:', len(decoded) if decoded else 0)
                srcs = helpers.scrape_sources(decoded)
                print('[netcine] fontes extraídas do base64:', srcs)
                if srcs:
                    chosen = helpers.pick_source(helpers.sort_sources_list(srcs))
                    print('[netcine] fonte escolhida (base64):', chosen)
                    return chosen + helpers.append_headers(headers)
            else:
                print('[netcine] sem base64 inline')
        except Exception as e:
            print('[netcine] erro ao processar base64:', repr(e))

        # 2) helpers.scrape_sources no player_html
        try:
            srcs = helpers.scrape_sources(player_html)
            print('[netcine] scrape_sources retornou:', srcs)
            if srcs:
                chosen = helpers.pick_source(helpers.sort_sources_list(srcs))
                print('[netcine] fonte escolhida (scrape_sources):', chosen)
                return chosen + helpers.append_headers(headers)
        except Exception as e:
            print('[netcine] erro em scrape_sources:', repr(e))

        # 3) <source src=...>
        try:
            sources = re.findall(r'<source[^>]*\s+src=["\']([^"\']+)["\']', player_html, re.IGNORECASE)
            print('[netcine] <source> encontrados:', sources)
            if sources:
                src_list = [{'file': s} for s in sources]
                try:
                    chosen = helpers.pick_source(helpers.sort_sources_list(src_list))
                    print('[netcine] fonte escolhida (<source>):', chosen)
                    return chosen + helpers.append_headers(headers)
                except Exception:
                    print('[netcine] fallback: retornando última <source>')
                    return sources[-1] + helpers.append_headers(headers)
        except Exception as e:
            print('[netcine] erro ao procurar <source>:', repr(e))

        # 4) JS players file: "..." ou file: '...'
        try:
            js_files = re.findall(r'file\s*:\s*["\']([^"\']+)["\']', player_html, re.IGNORECASE)
            print('[netcine] arquivos JS (file: ...):', js_files)
            if js_files:
                print('[netcine] retornando última entrada JS file:', js_files[-1])
                return js_files[-1] + helpers.append_headers(headers)
        except Exception as e:
            print('[netcine] erro ao procurar js files:', repr(e))

        print('[netcine] Video Link Not Found')
        raise ResolverError('Video Link Not Found')
