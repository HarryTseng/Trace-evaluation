import yaml

COLLECTOR_IP = "192.168.50.56"
HEAD_SAMPLING_RATE = 0  # 0是tail

SERVICES_CONFIG = {
    "productpage": {
        "context": "./productpage",
        "port": "9080:9080",
        "command": "gunicorn --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:9080 productpage:app",
        "env": {}
    },
    "reviews": {
        "context": "./reviews",
        "port": "9081:9080",
        "command": None,
        "env": {
            "SERVICE_VERSION": "v2",
            "ENABLE_RATINGS": "true",
            "STAR_COLOR": "black"
        }
    },
    "ratings": {
        "context": "./ratings",
        "port": "9082:9080",
        "command": None,
        "env": {
            "SERVICE_VERSION": "v1"
        }
    },
    "details": {
        "context": "./details",
        "port": "9083:9080",
        "command": None,
        "env": {
            "SERVICE_VERSION": "v1"
        }
    }
}
# =========================================================

def generate():
    compose_data = {
        "services": {},
        "networks": {
            "bookinfo-net": {
                "driver": "bridge"
            }
        }
    }

    compose_data["services"]["collector"] = {
        "profiles": ["collector"],
        "image": "otel/opentelemetry-collector-contrib:latest",
        "command": ["--config=/etc/otelcol/config.bookinfo.yaml"],
        "volumes": [
            "./config.bookinfo.yaml:/etc/otelcol/config.bookinfo.yaml",
            "./traces_bookinfo.json:/tmp/traces_bookinfo.json"
        ],
        "ports": [
            "4317:4317",
            "4318:4318",
            "8888:8888",
            "8080:8080"
        ],
        "networks": ["bookinfo-net"]
    }

    # 配置參數
    for name, cfg in SERVICES_CONFIG.items():
        env_vars = [
            f"SERVICE_NAME={name}",
            f"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://collector:4318/v1/traces"
        ]

        for k, v in cfg["env"].items():
            env_vars.append(f"{k}={v}")

        if HEAD_SAMPLING_RATE > 0:
            env_vars.append(f"HEAD_SAMPLING_RATE={HEAD_SAMPLING_RATE}")

        svc_dict = {
            "profiles": ["service"],
            "build": {
                "context": cfg["context"]
            },
            "ports": [cfg["port"]],
            "extra_hosts": [
                f"collector:{COLLECTOR_IP}"
            ],
            "environment": env_vars,
            "networks": ["bookinfo-net"]
        }

        if cfg["command"]:
            svc_dict["command"] = cfg["command"]

        compose_data["services"][name] = svc_dict

    with open("docker-compose.yaml", "w", encoding="utf-8") as f:
        yaml.dump(compose_data, f, sort_keys=False, allow_unicode=True)

    print(f"Successfully generated docker-compose.yaml with Collector IP: {COLLECTOR_IP} and Head Sampling Rate: {HEAD_SAMPLING_RATE}")

if __name__ == "__main__":
    generate()