import os
import json
import requests
from datetime import datetime, timedelta

# Configurações da API Amadeus (https://developers.amadeus.com)
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID", "SEU_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET", "SEU_CLIENT_SECRET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL gerada no Microsoft Teams Workflows

ORIGIN = "LIS"
DESTINATION = "POA"
DEPARTURE_DATES = ["2026-12-30", "2026-12-31"]
MIN_STAY_DAYS = 25
MAX_STAY_DAYS = 35
TARGET_PRICE_EUR = 1100.00


def get_access_token():
    auth_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    res = requests.post(
        auth_url,
        data={
            "grant_type": "client_credentials",
            "client_id": AMADEUS_CLIENT_ID,
            "client_secret": AMADEUS_CLIENT_SECRET,
        },
    )
    res.raise_for_status()
    return res.json()["access_token"]


def send_teams_notification(flight_data):
    if not WEBHOOK_URL:
        print("WEBHOOK_URL não configurada.")
        return

    teams_card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "✈️ Alerta de Voo TAP Direto (LIS ⇄ POA)",
                            "weight": "Bolder",
                            "size": "Medium",
                            "color": "Accent",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {
                                    "title": "Melhor Preço:",
                                    "value": f"€ {flight_data['price']:.2f}",
                                },
                                {
                                    "title": "Data de Ida:",
                                    "value": flight_data["departure"],
                                },
                                {
                                    "title": "Data de Volta:",
                                    "value": flight_data["return"],
                                },
                                {
                                    "title": "Duração:",
                                    "value": f"{flight_data['days']} dias",
                                },
                            ],
                        },
                    ],
                },
            }
        ],
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(teams_card))

    if response.status_code in [200, 202]:
        print("Notificação enviada com sucesso para o Teams.")
    else:
        print(f"Falha ao enviar notificação para o Teams: {response.status_code} - {response.text}")


def check_tap_direct_flights():
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    search_url = "https://test.api.amadeus.com/v2/shopping/flight-offers"

    best_offers = []

    for dep_str in DEPARTURE_DATES:
        dep_date = datetime.strptime(dep_str, "%Y-%m-%d")

        for stay in range(MIN_STAY_DAYS, MAX_STAY_DAYS + 1):
            ret_date = dep_date + timedelta(days=stay)
            ret_str = ret_date.strftime("%Y-%m-%d")

            params = {
                "originLocationCode": ORIGIN,
                "destinationLocationCode": DESTINATION,
                "departureDate": dep_str,
                "returnDate": ret_str,
                "adults": 1,
                "includedAirlineCodes": "TP",  # Apenas voos operados pela TAP
                "nonStop": "true",             # Apenas voos diretos
                "currencyCode": "EUR",
                "max": 3,
            }

            resp = requests.get(search_url, headers=headers, params=params)
            if resp.status_code != 200:
                continue

            data = resp.json().get("data", [])
            for offer in data:
                total_price = float(offer["price"]["total"])
                best_offers.append({
                    "departure": dep_str,
                    "return": ret_str,
                    "days": stay,
                    "price": total_price,
                })

    if not best_offers:
        print("Nenhum voo direto da TAP encontrado para os parâmetros.")
        return

    best_offers.sort(key=lambda x: x["price"])
    cheapest = best_offers[0]

    print(
        f"Menor valor encontrado: €{cheapest['price']:.2f} "
        f"(Ida: {cheapest['departure']} | Volta: {cheapest['return']} - {cheapest['days']} dias)"
    )

    if cheapest["price"] <= TARGET_PRICE_EUR and WEBHOOK_URL:
        send_teams_notification(cheapest)


if __name__ == "__main__":
    check_tap_direct_flights()
