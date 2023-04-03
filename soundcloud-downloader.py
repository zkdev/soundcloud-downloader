import argparse
import dataclasses
import json
import os
import os.path
import random
import re
import string
import subprocess
import time
import urllib

from bs4 import BeautifulSoup
import requests


@dataclasses.dataclass(frozen=True)
class Track:
    id: str
    name: str
    artist_name: str
    track_url: str
    track_auth_token: str


def get_soup(url: str) -> BeautifulSoup:
    html = requests.get(parsed.from_url)
    return BeautifulSoup(
        html.text,
        features='html.parser',
    )


def find_data(soup: BeautifulSoup) -> dict:
    data_tag = soup.find('script', string=re.compile('window.__sc_hydration'))
    return json.loads(data_tag.contents[0].lstrip('window.__sc_hydration = ').rstrip(';'))


def parse_track(data: dict) -> Track:
    track_id = data[7]['data']['id']
    track_name = data[7]['data']['title']
    artist_name = data[7]['data']['user']['username']

    track_auth_token = data[-1]['data']['track_authorization']

    # https://api-v2.soundcloud.com/media/soundcloud:tracks:291783692/0d7ab0a0-4595-475c-b4f0-55cbd24c2fec/stream/progressive
    track_url = data[7]['data']['media']['transcodings'][0]['url']
    track_url = track_url.replace(f'https://api-v2.soundcloud.com/media/soundcloud:tracks:{track_id}/', '').replace('/stream/progressive', '')
    track_url = f'https://api-v2.soundcloud.com/media/soundcloud:tracks:{track_id}/{track_url}'

    return Track(
        id=track_id,
        name=track_name,
        artist_name=artist_name,
        track_url=track_url,
        track_auth_token=track_auth_token,
    )


def download_track(
    client_id: str,
    track_url: str,
    out_file_name: str | None,
    max_retries: int,
):
    soup = get_soup(track_url)
    track_data = find_data(soup)
    track = parse_track(track_data)

    print(f'downloading "{track.artist_name} - {track.name}"')
    print(f'using client_id "{parsed.client_id}"')

    out_file_name = out_file_name or f'{track.name.replace(" ", "_")}.mp3'
    out_file = os.path.abspath(out_file_name)

    if os.path.isfile(out_file):
        os.remove(out_file)

    for _ in range(max_retries):
        try:
            download_data = requests.get(
                url=track.track_url,
                params={
                    'client_id': client_id,
                    'track_authorization': track.track_auth_token,
                },
            ).json()
            download_url = download_data['url']
            break
        except KeyError:
            print('cdn not ready, retrying...')
            time.sleep(1) # throttle requests
    else:
        raise RuntimeError(f'{max_retries=} exceeded, raising to prevent infinite-loop')

    print('stream data received, downloading...')

    subprocess.run(
        [
            'ffmpeg',
            '-i',
            download_url,
            out_file_name,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    print(f'successfully downloaded to {out_file}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--client-id',
        required=False,
        default='a3e059563d7fd3372b49b37f00a00bcf',
    )
    parser.add_argument(
        '--out-file',
        required=False,
        default=None,
        help='defaults to song title',
    )
    parser.add_argument(
        '--from-url',
        required=True,
    )
    parser.add_argument(
        '--max-retries',
        required=False,
        default=10,
        type=int,
    )

    parsed = parser.parse_args()

    download_track(
        client_id=parsed.client_id,
        track_url=parsed.from_url,
        out_file_name=parsed.out_file,
        max_retries=parsed.max_retries,
    )

