"""Validated tool interface shared by all concrete tools."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, ValidationError


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ToolOutput(BaseModel):
    content: str
    is_error: bool = False


class Tool(ABC):
    name: str
    description: str
    arguments_type: type[ToolArguments]

    def definition(self) -> dict[str, object]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments_type.model_json_schema(),
            },
        }

    def invoke(self, raw_arguments: dict[str, object]) -> ToolOutput:
        try:
            arguments = self.arguments_type.model_validate(raw_arguments)
            output = self.execute(arguments)
            return output if isinstance(output, ToolOutput) else ToolOutput(content=output)
        except ValidationError as error:
            return ToolOutput(content=f"Invalid arguments for {self.name}:\n{error}", is_error=True)
        except Exception as error:
            return ToolOutput(content=f"{type(error).__name__}: {error}", is_error=True)

    @abstractmethod
    def execute(self, arguments: ToolArguments) -> str | ToolOutput:
        raise NotImplementedError
