import json
import requests

STITCHER_URL = 'http://host.docker.internal:8090'

STITCHER_JS_URL = 'http://ecdysis01.local:8090'

ERROR_MSG_KEY = 'ERROR'


def list_upload_files():
    api_list_url = STITCHER_URL + '/list-upload-files/'
    all_data = []
    offset = 0
    limit = 100

    while True:
        print('*'*100)
        params = {
            'offset': offset,
            'limit': limit,
            'approved': True
        }
        print(params)

        try:
            response = requests.get(api_list_url, params=params)
        except Exception as e:
            print(e)
            break

        if response.status_code == 200:
            data = response.json()
            if not data:
                break

            all_data.extend(data)
            offset += limit
        else:
            print(f"Error: {response.status_code}")
            break

    return all_data


def get_upload_file(guid):
    api_list_url = STITCHER_URL + '/list-upload/'
    try:
        response = requests.get(api_list_url, params={'guid': guid})
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return {ERROR_MSG_KEY: response.status_code}
    except Exception as e:
        print(e)
        return {ERROR_MSG_KEY: e}


def patch_upload_file(guid, data):
    api_url = STITCHER_URL + f'/update-record/{guid}'
    try:
        response = requests.patch(api_url, data=json.dumps(data))
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return {ERROR_MSG_KEY: response.status_code}
    except Exception as e:
        print(e)
        return {ERROR_MSG_KEY: e}


def delete_upload_file(guid):
    api_url = STITCHER_URL + f'/delete/{guid}'
    try:
        response = requests.delete(api_url)
        if response.status_code in [200, 204]:
            return {'message': f'success code {response.status_code}'}
        else:
            return {ERROR_MSG_KEY: response.status_code}
    except Exception as e:
        print(e)
        return {ERROR_MSG_KEY: e}


def get_root_message():
    api_url = STITCHER_URL
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return {ERROR_MSG_KEY: response.status_code}
    except Exception as e:
        print(e)
        return {ERROR_MSG_KEY: e}


def get_stitcher_stats():
    api_url = STITCHER_URL + '/stats/'
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return {ERROR_MSG_KEY: response.status_code}
    except Exception as e:
        print(e)
        return {ERROR_MSG_KEY: e}
