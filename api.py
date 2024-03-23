import json
import os
import pandas as pd
import numpy as np
import requests
from pyotp import TOTP
from dotenv import load_dotenv

load_dotenv(verbose=True, override=True)

AUTH_SECRET = os.getenv('AUTH_SECRET')
USER_ID = os.getenv('USER_ID')
PASS_ID = os.getenv('PASS_ID')
SITEKEY = os.getenv('SITEKEY')
CLIENT_ID = os.getenv('CLIENT_ID')
NOTIFICATION_TOKEN = os.getenv('NOTIFICATION_TOKEN')

import sys

sys.path.append('../')

from common.captcha_bypass import CaptchaBypass


def monthly_count(data):
    # Plu collected per month
    data['amount'] = data['amount'].astype(float)
    valids = data[data['reason'] != "Rejected by admin"]
    valids['createdAt'] = pd.to_datetime(valids['createdAt'])
    per = valids.createdAt.dt.to_period("M")
    g = valids.groupby(per)
    # print(g.sum()['amount']) # stopped working TypeError: datetime64 type does not support sum operations

    # print(g['amount'].sum())  # new syntax
    # print(g['plu_price'].mean())
    # print(g['plu_price'].max())
    # print(g['plu_price'].min())

    return g.agg(Sum=('amount', np.sum), plu_mean=('plu_price', np.mean), plu_max=('plu_price', np.max),
                 plu_min=('plu_price', np.min)).round(2)


def get_current_plu_price():
    url = "https://api.coingecko.com/api/v3/simple/price/?ids=pluton&vs_currencies=gbp"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/116.0',
        'Accept': '*/*',
        'Referer': 'https://beincrypto.com/',
        'Content-Type': 'application/json',
        'Origin': 'https://beincrypto.com',
        'Connection': 'keep-alive',
    }

    response = requests.request("GET", url, headers=headers)
    return response.json()['pluton']['gbp']


class PlutusApi(object):
    def __init__(self, user_id, pass_id, auth_id, client_id):
        self.user_field_id = user_id
        self.pass_field_id = pass_id
        self.auth_field_id = auth_id
        self.client_field_id = client_id
        self.session = None

    def login(self):

        url = "https://authenticate.plutus.it/auth/login"

        g_response = CaptchaBypass(SITEKEY, url).bypass()

        totp = TOTP(self.auth_field_id)
        token = totp.now()

        payload = {
            "email": self.user_field_id,
            "token": token,
            "password": self.pass_field_id,
            "captcha": g_response,
            "client_id": self.client_field_id
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:106.0) Gecko/20100101 Firefox/106.0",
            "Accept": "application/json",
            "Referer": "https://dex.plutus.it/",
            "Content-Type": "application/json",
            "Origin": "https://dex.plutus.it",
        }

        self.session = requests.Session()
        response = self.session.post(url, json=payload, headers=headers)  # login

        # Sometime request will fail because otp token timed out so retry once more

        if 'id_token' not in response.json():
            token = totp.now()

            payload = {
                "email": self.user_field_id,
                "token": token,
                "password": self.pass_field_id,
                "captcha": g_response,
                "client_id": self.client_field_id
            }
            response = self.session.post(url, json=payload, headers=headers)

        headers = {
            "Authorization": "Bearer " + response.json()['id_token'],
            "Connection": "keep-alive",
        }

        self.session.headers.update(headers)

        # return session

    # Rewards
    def get_rewards(self):

        if not self.session:
            self.login()

        response = self.session.get("https://api.plutus.it/platform/transactions/pluton")

        if response.status_code != 200:
            # push_notification(NOTIFICATION_TOKEN, "Plutus Rewards", "Lambda Failed to get transactions 💀")
            return {
                "statusCode": response.status_code,
                "body": {
                    'message': 'failed to get transactions',
                }
            }

        data = json.loads(response.text)
        data = pd.json_normalize(data)

        float_values = ['amount', 'rebate_rate', 'base_rate', 'staking_rate', 'contis_transaction.transaction_amount',
                        'fiat_transaction.card_transactions.api_response.TransactionAmount']

        for column in float_values:
            data[column] = data[column].astype(float)

        data['updatedAt'] = pd.to_datetime(data['updatedAt'])
        data['createdAt'] = pd.to_datetime(data['createdAt'])
        data.drop('contis_transaction', axis=1, inplace=True)
        # data.dropna(subset=['contis_transaction.description', 'fiat_transaction.card_transactions.description'], how='all',
        #             inplace=True)

        na_condition = data[
            ['contis_transaction.description', 'fiat_transaction.card_transactions.description']].isna().all(axis=1)

        # Create a mask for rows where 'type' is not 'REBATE_BONUS'
        not_rebate_condition = data['type'] != 'REBATE_BONUS'

        # Combine conditions
        condition_to_drop = na_condition & not_rebate_condition

        # Drop rows based on the combined condition
        data = data[~condition_to_drop]

        data['contis_transaction.description'].fillna(data['fiat_transaction.card_transactions.description'],
                                                      inplace=True)
        data['contis_transaction.transaction_amount'].fillna(
            data['fiat_transaction.card_transactions.api_response.TransactionAmount'].mul(100), inplace=True)
        data['contis_transaction.transaction_amount'] = data['contis_transaction.transaction_amount'].astype(float)

        nas = data[(data['contis_transaction.transaction_amount'].isna()) & (data['type'] != 'REBATE_BONUS')]

        for index, row in nas.iterrows():
            rebate = data[(data["exchange_rate_id"] == row["exchange_rate_id"]) & (
                data["contis_transaction.transaction_amount"].notnull())].head(1).squeeze()
            row['contis_transaction.transaction_amount'] = row[
                'fiat_amount_rewarded']  # Maybe keep as na because perk transaction includes total cost?
            row['contis_transaction.description'] = rebate['contis_transaction.description']
            row['contis_transaction.currency'] = rebate['contis_transaction.currency']

            data.iloc[index] = row

        # data['contis_transaction.transaction_amount'] = data['contis_transaction.transaction_amount'].astype(float)
        # data['contis_transaction.transaction_amount'] = data['contis_transaction.transaction_amount'] / 100

        # plu price at time of transaction in pence
        for index, row in data.iterrows():
            if row['rebate_rate'] == 0.0:
                # fiat_amount_rewarded is 100% of transaction so no need to /100
                data.loc[index, 'plu_price'] = row['fiat_amount_rewarded'] / row['amount']
            else:
                data.loc[index, 'plu_price'] = ((row['contis_transaction.transaction_amount'] / 100) * row[
                    'rebate_rate']) / row['amount']

        return data

    # Not working
    def get_card_balance(self):

        if not self.session:
            self.session = self.login()

        response = self.session.get(
            "https://api.plutus.it/platform/consumer/balance")  # {'errors': ['disabled: use cards v3 endpoint']}

        if response.status_code == 200:
            data = json.loads(response.text)
            return float(str(data['AvailableBalance'])[:-2] + '.' + str(data['AvailableBalance'])[-2:])

    def get_transactions(self, limit=300):

        if not self.session:
            self.session = self.login()

        url = "https://hasura.plutus.it/v1alpha1/graphql"

        payload = json.dumps({
            "operationName": "transactions_view",
            "variables": {
                "offset": 0,
                "limit": limit,
                "from": None,
                "to": None
            },
            "query": "query transactions_view($offset: Int, $limit: Int, $from: timestamptz, $to: timestamptz, $type: String) {\n  transactions_view_aggregate(\n    where: {_and: [{date: {_gte: $from}}, {date: {_lte: $to}}]}\n  ) {\n    aggregate {\n      totalCount: count\n      __typename\n    }\n    __typename\n  }\n  transactions_view(\n    order_by: {date: desc}\n    limit: $limit\n    offset: $offset\n    where: {_and: [{date: {_gte: $from}}, {date: {_lte: $to}}, {type: {_eq: $type}}]}\n  ) {\n    id\n    model\n    user_id\n    currency\n    amount\n    date\n    type\n    is_debit\n    description\n    __typename\n  }\n}\n"
        })

        response = self.session.post(url, data=payload)

        return response.json()['data']['transactions_view']

    def get_perks(self):

        if not self.session:
            self.session = self.login()

        perks = []
        response = self.session.get("https://api.plutus.it/platform/perks")
        if response.status_code == 200:
            perks_data = json.loads(response.text)

            # perks_data['total_perks_granted']

            for dic_ in perks_data['perks']:
                print(dic_['label'])
                perks.append({'id': dic_['id'], 'perk': dic_['label'], 'percent_complete': dic_["percent_spent"],
                              'max_monthly_fiat_reward': dic_["max_mothly_fiat_reward"],
                              "available": dic_["available"]})

        return perks

    def get_selected_next_month_perks(self):

        if not self.session:
            self.login()

        perks = []
        response = self.session.get("https://api.plutus.it/platform/perks")
        if response.status_code == 200:
            perks_data = json.loads(response.text)

            # perks_data['total_perks_granted']

            for dic_ in perks_data['next_month_perks']:
                print(dic_['label'])
                perks.append(
                    {'id': dic_['id'], 'perk': dic_['label'], 'max_monthly_fiat_reward': dic_["max_mothly_fiat_reward"],
                     "available": dic_["available"]})

        return perks

    def get_perk_spots_left(self):
        if not self.session:
            self.login()
        response = self.session.get("https://api.plutus.it/platform/perks")
        if response.status_code == 200:
            return json.loads(response.text)['available']
        return None

    def get_total_perks_granted(self):

        if not self.session:
            self.login()

        response = self.session.get("https://api.plutus.it/platform/perks")
        if response.status_code == 200:
            perks_data = json.loads(response.text)

        return perks_data['total_perks_granted']

    def perks_api(self):
        if not self.session:
            self.login()

        response = self.session.get("https://api.plutus.it/platform/configurations/perks")
        if response.status_code == 200:
            return json.loads(response.text)
        return None

    def get_all_perks(self):
        return [dic_['label'] for dic_ in self.perks_api()['perks']]

    def get_all_perks_with_img(self):
        print(self.perks_api()['perks'])
        return {dic_['label']: dic_['image_url'] for dic_ in self.perks_api()['perks']}


if __name__ == '__main__':
    AUTH_SECRET = os.getenv('AUTH_SECRET')
    USER_ID = os.getenv('USER_ID')
    PASS_ID = os.getenv('PASS_ID')
    SITEKEY = os.getenv('SITEKEY')
    CLIENT_ID = os.getenv('CLIENT_ID')
    NOTIFICATION_TOKEN = os.getenv('NOTIFICATION_TOKEN')

    api = PlutusApi(USER_ID, PASS_ID, AUTH_SECRET, CLIENT_ID)
    # session = api.login()

    url = "https://hasura.plutus.it/v1alpha1/graphql"

    payload = "{\"operationName\":\"getBalance\",\"variables\":{\"currency\":\"GBP\"},\"query\":\"query getBalance($currency: enum_fiat_balance_currency!) {\\n  fiat_balance(where: {currency: {_eq: $currency}}) {\\n    id\\n    user_id\\n    currency\\n    amount\\n    created_at\\n    updated_at\\n    __typename\\n  }\\n  card_transactions_aggregate(\\n    where: {type: {_eq: \\\"AUTHORISATION\\\"}, status: {_eq: \\\"APPROVED\\\"}}\\n  ) {\\n    aggregate {\\n      sum {\\n        billing_amount\\n        __typename\\n      }\\n      __typename\\n    }\\n    __typename\\n  }\\n}\\n\"}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/118.0",
        "Accept": "*/*",
        "Accept-Language": "en-GB,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://dex.plutus.it/",
        "content-type": "application/json",
        "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJodHRwczovL2hhc3VyYS5pby9qd3QvY2xhaW1zIjp7IngtaGFzdXJhLWRlZmF1bHQtcm9sZSI6InVzZXIiLCJ4LWhhc3VyYS1hbGxvd2VkLXJvbGVzIjpbInVzZXIiXSwieC1oYXN1cmEtdXNlci1pZCI6ImVmMjM0M2FlLTE4ZjUtNGRkNS04OTRjLWQ5YWM3NzA1YjJjYSJ9LCJodHRwczovL2RleC5wbHV0dXMuaXQvY2xhaW1zL2dyb3VwcyI6WyJ1c2VyIl0sIm1mYV9lbmFibGVkIjp0cnVlLCJhdXRoMF9pZCI6ImVmMjM0M2FlLTE4ZjUtNGRkNS04OTRjLWQ5YWM3NzA1YjJjYSIsImVtYWlsIjoiZGF2aWQtYWRlbmlqaUBob3RtYWlsLmNvLnVrIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsInVzZXJfYmxvY2tlZCI6ZmFsc2UsInBlbmRpbmdfaXNzdWUiOm51bGwsImludGVybmF0aW9uYWwiOmZhbHNlLCJzdXNwZW5kZWRfYXQiOm51bGwsImxvY2FsX2N1cnJlbmN5IjoiR0JQIiwib25ib2FyZGluZ19zdGVwIjoiY29tcGxldGVkIiwiaWF0IjoxNjk2MTUxNjE5LCJleHAiOjE2OTYxNTE5MTksImF1ZCI6IlZ5bHpmaXd0SHlKaW5rRXJkQXRhdm9ISCIsImlzcyI6IlBMVVRVUyIsInN1YiI6ImVmMjM0M2FlLTE4ZjUtNGRkNS04OTRjLWQ5YWM3NzA1YjJjYSJ9.Xlg9EO3pguMTQzSxbX26eu48mrVx-4WWYXFk7audIyHgQo6yPkjEFSHK1vVu3AEjOyoOh2j6wH3HmUIERtLElVqqWJQpdkCMaFFQuNh4I2QN6bTOw-VBpsYVmdlxxlvMtR5h_MD7xcYJWo04UbnTh3T5n993ew-gbKN9CbvWCc9LpvYNguQEJIHG-NQH_ujFAnZC47nMuc4e5Sz7w2il1Y5gWDHJR17eEForUqeBL2lOp4wpEbBvKDd2G7texF5vRYpnr-A3-NqVPptSE7qirYG-i22e3Df5NRDhE__4Dkx1Bi-FS_4kmSRYjpE5pwx4JXdKh9b5mjPmAtqbfBYJgggALp06b9jfkFc-vQIrdFGe0GFtp3EsLz8RSXrGlYQGNecfIbdf7B5E9WGDF__nvZPvrNm2JcuA8umSO_mvl74SSnF7waJZ0u2joirsVbqZFnni2O-hARj1z3wXc1ONR4BuUUJx7XkU4lS40lHOU1yQfGW17_DIwv1oCzgN0RQV4w1m2Kx3S3aFNe1C8XX7tn1JBjxEd65Quz7owZoP3vGMmP2osK_iyLXK84lCZSyZ_b99oRw8xWis_dxI1Y_HPXbqiHiHslELbTbxfLGJwWHdDihXw8-c_xqpa_ZSL8-d6w4aGo1MDtkH_dTXYlX7nQJlI3ENL6jKrylPvm1vg0A",
        "Origin": "https://dex.plutus.it",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "TE": "trailers"
    }

    response = requests.request("POST", url, json=payload, headers=headers)

    print(response.text)

    rewards = api.get_rewards()

    # count = monthly_count(transactions)

    valids = rewards[rewards['reason'] != "Rejected by admin"]
    valids['createdAt'] = pd.to_datetime(valids['createdAt'])
    per = valids.createdAt.dt.to_period("M")
    g = valids.groupby(per)
    # print(g.sum()['amount']) # stopped working TypeError: datetime64 type does not support sum operations
    print(g['amount'].sum())  # new syntax

    transactions = api.get_transactions()
    txn = pd.DataFrame(transactions)

    perks = api.get_all_perks()
