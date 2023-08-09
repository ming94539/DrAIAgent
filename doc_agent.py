import logging
import re
from typing import Optional, AsyncGenerator
import typing
from vocode.streaming.agent import LLMAgent
from vocode.streaming.models.agent import AgentConfig, LLMAgentConfig
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.agent.factory import AgentFactory

def text_preprocess(str):
    return str.lower().strip()

class DoctorAgent(LLMAgent):
    def __init__(self, agent_config: LLMAgentConfig):
        super().__init__(agent_config=agent_config)
        self.call_profile = {
            "name": {"prompt": "Ask me for my full name, don't add any other unnecessary words" ,"value": None},
            "date of birth": {"prompt": "ask me for my date of birth, don't add any other unnecessary words" ,"value": None},
            "insurance name": {"prompt": "ask me for my insurance name, don't add any other unnecessary words" ,"value": None},
            "insurance ID": {"prompt": "ask me for my insurance id, don't add any other unnecessary words" ,"value": None},
            "referral": {"prompt": "ask me for my referral, don't be too verbose" ,"value": None},
            "chief medical complaint": {"prompt": "ask me for my chief medical complaint, don't be too verbose" ,"value": None},
            "address": {"prompt": "ask me for my address, don't be too verbose" ,"value": None},
            "email": {"prompt": "ask me for my email, don't be too verbose" ,"value": None},
        }

    async def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        self.logger.debug("LLM generating response to human input")        
        # default interrupt action
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            self.memory.append(self.get_memory_entry(human_input, cut_off_response))
            yield cut_off_response
            return
        self.memory.append(self.get_memory_entry(human_input, ""))
        # default first response action
        if self.is_first_response and self.first_response:
            self.logger.debug("First response is cached")
            self.is_first_response = False
            sentences = self._agen_from_list([self.first_response])
        else:
           for key in self.call_profile:
               for response in self.memory:
                   if text_preprocess(key) in text_preprocess(response):
                       self.logger.debug("key",key,"found")
                       self.call_profile[key]["value"] = response
    
           self.logger.debug("Filling in self.call_profile")
           for key,val in self.call_profile.items():
                self.logger.debug(key,val)
                if val is None:
                    human_input += self.call_profile[key]["prompt"]
                    break

        self.logger.debug("Creating LLM prompt")
        prompt = self.create_prompt(human_input)
        self.logger.debug("Streaming LLM response")
        sentences = self._stream_sentences(prompt)

        # Default processing
        response_buffer = ""
        async for sentence in sentences:
            sentence = sentence.replace(f"{self.sender}:", "")
            sentence = re.sub(r"^\s+(.*)", r" \1", sentence)
            response_buffer += sentence
            self.memory[-1] = self.get_memory_entry(human_input, response_buffer)

            yield sentence



class DoctorAgentFactory(AgentFactory):
    def create_agent(
        self, agent_config: AgentConfig, logger: Optional[logging.Logger] = None
    ) -> BaseAgent:
        return DoctorAgent(
            agent_config=typing.cast(LLMAgentConfig, agent_config),
        )