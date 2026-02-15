from dataclasses import dataclass

PublicMetadataValue = str | int | bool

@dataclass
class ClerkUserDTO:
    first_name: str
    last_name: str
    email_address: list[str]
    public_metadata: dict[str, PublicMetadataValue] | None = None
    delete_self_enabled: bool | None = None
    
    def to_dict(self) -> dict[str, str | list[str] | dict[str, PublicMetadataValue] | bool | None]:
        data: dict[str, str | list[str] | dict[str, PublicMetadataValue] | bool | None] = {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email_address": self.email_address,
        }
        if self.public_metadata is not None:
            data["public_metadata"] = self.public_metadata
        if self.delete_self_enabled is not None:
            data["delete_self_enabled"] = self.delete_self_enabled
        return data