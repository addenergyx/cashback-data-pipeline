import json
import pandas as pd
import numpy as np
import requests
from pyotp import TOTP

from common_shared_library.captcha_bypass import CaptchaBypass

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



class PlutusApi(object):
    def __init__(self, user_id, pass_id, auth_id, client_id):
        self.user_field_id = user_id
        self.pass_field_id = pass_id
        self.auth_field_id = auth_id
        self.client_field_id = client_id
        self.session = None

    def login(self):

        url = "https://authenticate.plutus.it/auth/login"
        public_sitekey = '6Le9DsMUAAAAAErnFJQ9diHca8Y1asRRW5sE8sBX'

        g_response = CaptchaBypass(public_sitekey, url).bypass()

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

        return response.json()

        # data = json.loads(response.text)
        # data = pd.json_normalize(data)
        #
        # float_values = ['amount', 'rebate_rate', 'base_rate', 'staking_rate', 'contis_transaction.transaction_amount',
        #                 'fiat_transaction.card_transactions.api_response.TransactionAmount']
        #
        # for column in float_values:
        #     data[column] = data[column].astype(float)
        #
        # data['updatedAt'] = pd.to_datetime(data['updatedAt'])
        # data['createdAt'] = pd.to_datetime(data['createdAt'])
        # data.drop('contis_transaction', axis=1, inplace=True)
        # # data.dropna(subset=['contis_transaction.description', 'fiat_transaction.card_transactions.description'], how='all',
        # #             inplace=True)
        #
        # na_condition = data[
        #     ['contis_transaction.description', 'fiat_transaction.card_transactions.description']].isna().all(axis=1)
        #
        # # Create a mask for rows where 'type' is not 'REBATE_BONUS'
        # not_rebate_condition = data['type'] != 'REBATE_BONUS'
        #
        # # Combine conditions
        # condition_to_drop = na_condition & not_rebate_condition
        #
        # # Drop rows based on the combined condition
        # data = data[~condition_to_drop]
        #
        # data['contis_transaction.description'].fillna(data['fiat_transaction.card_transactions.description'],
        #                                               inplace=True)
        # data['contis_transaction.transaction_amount'].fillna(
        #     data['fiat_transaction.card_transactions.api_response.TransactionAmount'].mul(100), inplace=True)
        # data['contis_transaction.transaction_amount'] = data['contis_transaction.transaction_amount'].astype(float)
        #
        # nas = data[(data['contis_transaction.transaction_amount'].isna()) & (data['type'] != 'REBATE_BONUS')]
        #
        # for index, row in nas.iterrows():
        #     rebate = data[(data["exchange_rate_id"] == row["exchange_rate_id"]) & (
        #         data["contis_transaction.transaction_amount"].notnull())].head(1).squeeze()
        #     row['contis_transaction.transaction_amount'] = row[
        #         'fiat_amount_rewarded']  # Maybe keep as na because perk transaction includes total cost?
        #     row['contis_transaction.description'] = rebate['contis_transaction.description']
        #     row['contis_transaction.currency'] = rebate['contis_transaction.currency']
        #
        #     data.iloc[index] = row
        #
        # # data['contis_transaction.transaction_amount'] = data['contis_transaction.transaction_amount'].astype(float)
        # # data['contis_transaction.transaction_amount'] = data['contis_transaction.transaction_amount'] / 100
        #
        # # plu price at time of transaction in pence
        # for index, row in data.iterrows():
        #     if row['rebate_rate'] == 0.0:
        #         # fiat_amount_rewarded is 100% of transaction so no need to /100
        #         data.loc[index, 'plu_price'] = row['fiat_amount_rewarded'] / row['amount']
        #     else:
        #         data.loc[index, 'plu_price'] = ((row['contis_transaction.transaction_amount'] / 100) * row[
        #             'rebate_rate']) / row['amount']
        #
        # return data

    # Not working
    # def get_card_balance(self):
    #
    #     if not self.session:
    #         self.session = self.login()
    #
    #     response = self.session.get(
    #         "https://api.plutus.it/platform/consumer/balance")  # {'errors': ['disabled: use cards v3 endpoint']}
    #
    #     if response.status_code == 200:
    #         data = json.loads(response.text)
    #         return float(str(data['AvailableBalance'])[:-2] + '.' + str(data['AvailableBalance'])[-2:])

    def get_transactions(self):

        if not self.session:
            print("Logging in")
            self.login()

        url = "https://hasura.plutus.it/v1alpha1/graphql"

        payload = json.dumps({
            "operationName": "transactions_view",
            "variables": {
                "offset": 0,
                # "limit": limit,
                "from": None,
                "to": None
            },
            "query": "query transactions_view($offset: Int, $limit: Int, $from: timestamptz, $to: timestamptz, $type: String) {\n  transactions_view_aggregate(\n    where: {_and: [{date: {_gte: $from}}, {date: {_lte: $to}}]}\n  ) {\n    aggregate {\n      totalCount: count\n      __typename\n    }\n    __typename\n  }\n  transactions_view(\n    order_by: {date: desc}\n    limit: $limit\n    offset: $offset\n    where: {_and: [{date: {_gte: $from}}, {date: {_lte: $to}}, {type: {_eq: $type}}]}\n  ) {\n    id\n    model\n    user_id\n    currency\n    amount\n    date\n    type\n    is_debit\n    description\n    __typename\n  }\n}\n"
        })

        response = self.session.post(url, data=payload)

        return response.json()['data']['transactions_view']
