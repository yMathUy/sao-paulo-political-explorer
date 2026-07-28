import requests


CHAMBER_API_URL = "https://dadosabertos.camara.leg.br/api/v2"


def get_sao_paulo_deputies():
    response = requests.get(
        f"{CHAMBER_API_URL}/deputados",
        params={
            "siglaUf": "SP",
            "itens": 100,
            "ordem": "ASC",
            "ordenarPor": "nome",
        },
        headers={
            "Accept": "application/json",
        },
        timeout=15,
    )

    response.raise_for_status()

    data = response.json()

    return data.get("dados", [])