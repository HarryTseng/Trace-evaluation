import os
import random
from fastapi import FastAPI, HTTPException, Request
import requests
from opentelemetry.trace import StatusCode
from opentelemetry import trace, propagate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

app = FastAPI()

SERVICE_NAME = os.getenv("SERVICE_NAME")
TARGET_URL = os.getenv("TARGET_URL")
UPSTREAM_ERROR_RATE = float(os.getenv("UPSTREAM_ERROR_RATE"))
DOWNSTREAM_ERROR_RATE = float(os.getenv("DOWNSTREAM_ERROR_RATE"))
TOPOLOGY_TYPE = os.getenv("TOPOLOGY_TYPE")

resource = Resource.create({"service.name": SERVICE_NAME})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://collector:4318/v1/traces")))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("my-experiment")

@app.get("/hello")

# 
def hello(request: Request):
    context = propagate.extract(request.headers)

    # 手動建立Span
    with tracer.start_as_current_span(f"{SERVICE_NAME}_Job", context=context, record_exception=False) as span:
        try:
            # 節點內部邏輯
            if random.random() < UPSTREAM_ERROR_RATE:
                raise Exception("Upstream Error Happen")
            
            # 把trace資訊注入header
            if TARGET_URL:
                headers = {}
                propagate.inject(headers)
                
                URLS = TARGET_URL.split(',') if TOPOLOGY_TYPE == "FAN_OUT" else [TARGET_URL]

                # 發request
                for URL in URLS:
                    res = requests.get(URL, headers=headers)
                    if res.status_code != 200:
                        span.add_event("request_fail", {"status_code": res.status_code})
                        raise Exception("Downstream Error")
                
                if random.random() < DOWNSTREAM_ERROR_RATE:
                    raise Exception("Downstream Error Happen")
            
            return {"status": "success"}
        
        except Exception as e:
            span.set_status(StatusCode.ERROR)
            span.set_attribute("error.msg", str(e))
            raise HTTPException(status_code=500, detail=str(e))