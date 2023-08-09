import logging
import os
from fastapi import FastAPI
from vocode.streaming.models.telephony import TwilioConfig
from pyngrok import ngrok

from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.server.base import (
    TwilioInboundCallConfig,
    TelephonyServer,
)
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig, PunctuationEndpointingConfig

from doc_agent import DoctorAgentFactory
from vocode.streaming.models.agent import LLMAgentConfig
import sys
from script import INITIAL_MESSAGE, PRE_PROMPT

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_manager = RedisConfigManager()

BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")
telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=LLMAgentConfig( # CHAT_GPT_AGENT_DEFAULT_MODEL_NAME wasnt supported for v1/completions endpoint
                initial_message=BaseMessage(text=INITIAL_MESSAGE),
                prompt_preamble=PRE_PROMPT,
                allowed_idle_time_seconds=25, #Other wise keeps cutting patient off
                end_conversation_on_goodbye=True,
                allow_agent_to_be_cut_off=False, #overlapping speeches was making it hard.
                generate_response=True,
                max_tokens = 40, # chatGPT likes to be verbose
            ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
            synthesizer_config=AzureSynthesizerConfig.from_telephone_output_device(),
            transcriber_config=DeepgramTranscriberConfig.from_telephone_input_device(
                endpointing_config=PunctuationEndpointingConfig()
            ),
        )
    ],
    agent_factory=DoctorAgentFactory(),
    logger=logger,
)

app.include_router(telephony_server.get_router())
