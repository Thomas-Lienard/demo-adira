import os
import yaml

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _load_yaml(filename: str) -> dict:
    with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_ontology() -> dict:
    return _load_yaml("ontology.yaml")


def load_semantic() -> dict:
    return _load_yaml("semantic.yaml")


def get_graph_data() -> dict:
    ontology = load_ontology()
    semantic = load_semantic()

    nodes = []
    edges = []

    colors = {
        "Region": "#2ac3de",
        "Commercial": "#bb9af7",
        "Client": "#7aa2f7",
        "Commande": "#ff9e64",
        "LigneCommande": "#e0af68",
        "Facture": "#9ece6a",
        "Paiement": "#73daca",
        "Produit": "#4ade80",
        "AppelCommercial": "#f472b6",
        "TicketClient": "#fb923c",
    }

    for name, entity in ontology.get("entity_types", {}).items():
        nodes.append({
            "data": {
                "id": name,
                "label": name,
                "type": "entity",
                "description": entity.get("description", ""),
                "table": entity.get("table", ""),
                "color": colors.get(name, "#c0caf5"),
                "properties": [
                    {"name": k, "source": v.get("source", ""), "description": v.get("description", "")}
                    for k, v in entity.get("properties", {}).items()
                ],
            }
        })

    for name, metric in semantic.get("metrics", {}).items():
        nodes.append({
            "data": {
                "id": f"metric_{name}",
                "label": metric.get("label", name),
                "type": "metric",
                "description": metric.get("description", ""),
                "sql": metric.get("sql", ""),
                "color": "#f7768e",
            }
        })
        for concept in metric.get("concepts", []):
            edges.append({
                "data": {
                    "id": f"metric_{name}_to_{concept}",
                    "source": f"metric_{name}",
                    "target": concept,
                    "label": "mesure",
                    "type": "metric_link",
                }
            })

    for rel in ontology.get("relationships", []):
        edges.append({
            "data": {
                "id": f"{rel['from']}_to_{rel['to']}",
                "source": rel["from"],
                "target": rel["to"],
                "label": rel.get("type", ""),
                "type": "relationship",
                "cardinality": rel.get("cardinality", ""),
            }
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "suggested_questions": ontology.get("suggested_questions", []),
    }


def get_ontology_context() -> str:
    ontology = load_ontology()
    semantic = load_semantic()
    return (
        "# ONTOLOGIE (concepts metier, vocabulaire, relations)\n"
        + yaml.dump(ontology, allow_unicode=True, default_flow_style=False)
        + "\n\n# COUCHE SEMANTIQUE (metriques, dimensions, regles de calcul)\n"
        + yaml.dump(semantic, allow_unicode=True, default_flow_style=False)
    )
