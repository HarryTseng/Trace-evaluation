import yaml

NUM_SERVICES = 5
TOPOLOGY_TYPE = "FAN_OUT"  #CHAIN, FAN_OUT, CONSTRAINT

def generate():
    services = {}
    
    for i in range(1, NUM_SERVICES + 1):
        name = f"service-{i}"
        targets = []

        if TOPOLOGY_TYPE in ["CHAIN", "CONSTRAINT"]:
            if i < NUM_SERVICES:
                targets.append(f"http://service-{i+1}:8000/hello")
        
        elif TOPOLOGY_TYPE == "FAN_OUT":
            if i == 1:
                for j in range(2, NUM_SERVICES + 1):
                    targets.append(f"http://service-{j}:8000/hello")

        if TOPOLOGY_TYPE == "CONSTRAINT":
            up_rate = round(0.01 * i, 2)
            down_rate = round(0.04 * i, 2)
        else:
            up_rate = 0.01
            down_rate = 0.04
        
        target_str = ",".join(targets)
        
        services[name] = {
            "profiles": ["service"],
            "build": ".",
            "command": "uvicorn main:app --host 0.0.0.0 --port 8000",
            "environment": [
                f"SERVICE_NAME={name}",
                f"TARGET_URL={target_str}",
                f"TOPOLOGY_TYPE={TOPOLOGY_TYPE}",
                f"UPSTREAM_ERROR_RATE={up_rate}",
                f"DOWNSTREAM_ERROR_RATE={down_rate}",
                "OTEL_COLLECTOR_URL=http://collector:4318/v1/traces"
            ],
            "ports": [f"{8000 + i - 1}:8000"],
        }

    services["collector"] = {
        "image": "otel/opentelemetry-collector-contrib:latest",
        "command": ["--config=/etc/otelcol/config.yaml"],
        "volumes": ["./config.yaml:/etc/otelcol/config.yaml",
                    "./:/etc/otelcol/"],
        "ports": ["4317:4317", "4318:4318", "8888:8888"]
    }

    with open("docker-compose.yaml", "w") as f:
        yaml.dump({"version": "3.8", "services": services}, f, sort_keys=False)
    
    print(f"Generated docker-compose.yaml with {TOPOLOGY_TYPE} topology.")

if __name__ == "__main__":
    generate()