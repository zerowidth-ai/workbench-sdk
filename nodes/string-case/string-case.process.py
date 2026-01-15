from typing import Any
import re

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  text = str(inputs.get("text", ""))
  case_type = settings.get("case", "lower")
  
  if case_type == "upper":
    return {"text": text.upper()}
    
  if case_type == "lower":
    return {"text": text.lower()}
    
  if case_type == "title":
    return {"text": text.title()}
    
  if case_type == "sentence":
    return {
      "text": '. '.join(s.capitalize() for s in text.split('. '))
    }
    
  if case_type == "camel":
    words = re.split(r'[^a-zA-Z0-9]', text.lower())
    return {
      "text": words[0] + ''.join(word.capitalize() for word in words[1:])
    }
    
  if case_type == "snake":
    return {
      "text": re.sub(r'[^a-zA-Z0-9]+', '_', text.lower()).strip('_')
    }
    
  if case_type == "kebab":
    return {
      "text": re.sub(r'[^a-zA-Z0-9]+', '-', text.lower()).strip('-')
    }
    
  return {"text": text} 