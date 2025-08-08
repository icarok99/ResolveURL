import re
import binascii
import json
from resolveurl.lib import helpers
from resolveurl.resolver import ResolveUrl, ResolverError
from resolveurl import common
from six.moves import urllib_parse
from resolveurl.lib.pyaes import AESModeOfOperationCBC, Decrypter

class DisneyCDNResolver(ResolveUrl):
    name = 'DisneyCDN'
    domains = ['disneycdn.net']
    # Captura host + ID do hash
    pattern = r'https?://(?:www\.)?(disneycdn\.net)/#([A-Za-z0-9]+)'

    def get_media_url(self, host, media_id):
        print(f"[DEBUG] Host recebido: {host}")
        print(f"[DEBUG] Media ID recebido: {media_id}")

        api_url = f'https://{host}/api/v1/video?id={media_id}'
        print(f"[DEBUG] URL da API montada: {api_url}")

        referer = f'https://{host}/'
        headers = {
            'User-Agent': common.FF_USER_AGENT,
            'Referer': referer,
            'Origin': referer
        }

        try:
            response = self.net.http_GET(api_url, headers=headers)
            enc_data = response.content
        except Exception as e:
            raise ResolverError(f'Erro ao fazer requisição: {e}')

        if isinstance(enc_data, bytes):
            enc_data = enc_data.decode('utf-8').strip()
        elif isinstance(enc_data, str):
            enc_data = enc_data.strip()
        else:
            raise ResolverError('Formato inesperado do conteúdo criptografado')

        print(f"[DEBUG] Dados recebidos da API (hex): {enc_data[:10000]}...")

        if not enc_data:
            raise ResolverError('Conteúdo criptografado não encontrado')

        try:
            enc_bytes = binascii.unhexlify(enc_data)
            print(f"[DEBUG] Dados convertidos para bytes: {enc_bytes[:10000]}...")
        except Exception as e:
            raise ResolverError(f'Erro ao converter hex para bytes: {e}')

        try:
            key = b'kiemtienmua911ca'
            iv = b'1234567890oiuytr'
            decrypter = Decrypter(AESModeOfOperationCBC(key, iv))
            dec_data = decrypter.feed(enc_bytes) + decrypter.feed()
            dec_str = dec_data.decode('utf-8') if isinstance(dec_data, bytes) else dec_data
            print(f"[DEBUG] Dados descriptografados: {dec_str[:10000]}...")
        except Exception as e:
            raise ResolverError(f'Erro na descriptografia: {e}')

        try:
            dec_json = json.loads(dec_str)
            print(f"[DEBUG] JSON decodificado: {json.dumps(dec_json)[:10000]}...")
        except Exception as e:
            raise ResolverError(f'Erro ao interpretar JSON: {e}')

        # Função auxiliar para achar links
        def find_urls_in_json(obj):
            urls = []
            if isinstance(obj, dict):
                for v in obj.values():
                    urls.extend(find_urls_in_json(v))
            elif isinstance(obj, list):
                for item in obj:
                    urls.extend(find_urls_in_json(item))
            elif isinstance(obj, str):
                if 'http' in obj:
                    urls.append(obj)
            return urls

        urls_found = find_urls_in_json(dec_json)
        print(f"[DEBUG] URLs encontradas: {urls_found}")

        if not urls_found:
            raise ResolverError('Nenhum link de stream encontrado no JSON')

        stream_url = urls_found[0]
        print(f"[DEBUG] Usando stream_url: {stream_url}")

        headers.update({'Origin': referer})
        return stream_url + helpers.append_headers(headers)
