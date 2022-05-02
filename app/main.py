from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.api_registry import api_registry
from app.config import ConfigClass


def create_app():
    """Initialize and configure app."""

    # settings = get_settings()

    app = FastAPI(
        title='Service Data Upload',
        description='Service for data upload usage',
        docs_url='/v1/api-doc',
        version=ConfigClass.VERSION,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins='*',
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    api_registry(app)

    instrument_app(app)

    return app


def instrument_app(app: FastAPI) -> None:
    """Instrument the application with OpenTelemetry tracing."""

    # settings = get_settings()

    if not ConfigClass.OPEN_TELEMETRY_ENABLED:
        return

    tracer_provider = TracerProvider(resource=Resource.create({SERVICE_NAME: ConfigClass.APP_NAME}))
    trace.set_tracer_provider(tracer_provider)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    AsyncPGInstrumentor().instrument()

    jaeger_exporter = JaegerExporter(
        agent_host_name=ConfigClass.OPEN_TELEMETRY_HOST, agent_port=ConfigClass.OPEN_TELEMETRY_PORT
    )

    tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
