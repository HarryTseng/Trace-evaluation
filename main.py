import os
import random
import asyncio
import httpx
from contextlib import asynccontextmanager # 新增
from fastapi import FastAPI, HTTPException, Request
from opentelemetry.trace import StatusCode
from opentelemetry import trace, propagate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased, ALWAYS_ON

# --- 原有配置保持不變 ---
SERVICE_NAME = os.getenv("SERVICE_NAME")
TARGET_URL = os.getenv("TARGET_URL")
UPSTREAM_ERROR_RATE = float(os.getenv("UPSTREAM_ERROR_RATE", 0))
DOWNSTREAM_ERROR_RATE = float(os.getenv("DOWNSTREAM_ERROR_RATE", 0))
HEAD_SAMPLING_RATE = float(os.getenv("HEAD_SAMPLING_RATE", "1.0"))
TOPOLOGY_TYPE = os.getenv("TOPOLOGY_TYPE")
URLS = TARGET_URL.split(',') if (TARGET_URL and TOPOLOGY_TYPE == "FAN_OUT") else ([TARGET_URL] if TARGET_URL else [])

custom_sampler = ParentBased(root=TraceIdRatioBased(HEAD_SAMPLING_RATE))

# --- OpenTelemetry 設定 ---
resource = Resource.create({"service.name": SERVICE_NAME})
provider = TracerProvider(
    resource=resource,
    sampler=custom_sampler
    )
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://collector:4318/v1/traces")))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("my-experiment")

# --- 關鍵改動：定義 Lifespan 管理連線池 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時建立全域 Client，此處可調整 pool 大小
    limits = httpx.Limits(max_keepalive_connections=100, max_connections=500)
    async with httpx.AsyncClient(limits=limits) as client:
        app.state.client = client
        yield
    # 關閉時會自動 clean up 連線

app = FastAPI(lifespan=lifespan)

@app.get("/hello")
async def hello(request: Request):
    context = propagate.extract(request.headers)
    # 從 app.state 取得共用的 client
    client = request.app.state.client 
    random_number = random.random()

    with tracer.start_as_current_span(f"{SERVICE_NAME}_Job", context=context, record_exception=False) as span:
        try:
            if random_number < UPSTREAM_ERROR_RATE:
                raise Exception("Upstream Error Happen")
            
            if TARGET_URL:
                headers = {}
                propagate.inject(headers)
                
                # 這裡不再使用 async with，直接使用全域 client
                if TOPOLOGY_TYPE == "FAN_OUT":
                    tasks = [client.get(URL, headers=headers) for URL in URLS]
                    responses = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for res in responses:
                        if isinstance(res, Exception) or res.status_code != 200:
                            span.add_event("request_fail", {"error": str(res)})
                            raise Exception("Downstream Error")
                else:
                    for URL in URLS:
                        res = await client.get(URL, headers=headers)
                        if res.status_code != 200:
                            span.add_event("request_fail", {"status_code": res.status_code})
                            raise Exception("Downstream Error")
                
                if random_number < UPSTREAM_ERROR_RATE + DOWNSTREAM_ERROR_RATE:
                    raise Exception("Downstream Error Happen")
            
            return {"status": "success"}
        
        except Exception as e:
            span.set_status(StatusCode.ERROR)
            span.set_attribute("error.msg", str(e))
            raise HTTPException(status_code=500, detail=str(e))