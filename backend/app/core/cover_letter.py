"""The cover letter bundle. Generated in the same LLM call as tailoring (to save free-tier
quota); this module holds the bundle type and fills in the private name placeholder locally."""

from pydantic import BaseModel

from app.llm.schemas import TailorResult

NAME_PLACEHOLDER = "{{NAME}}"


class CoverLetterBundle(BaseModel):
    cover_letter: str
    email_subject: str
    email_body: str
    whatsapp_message: str

    def as_dict(self) -> dict[str, str]:
        return self.model_dump()


def bundle_from(tailor: TailorResult) -> CoverLetterBundle:
    return CoverLetterBundle(
        cover_letter=tailor.cover_letter.strip(),
        email_subject=tailor.email_subject.strip(),
        email_body=tailor.email_body.strip(),
        whatsapp_message=tailor.whatsapp_message.strip(),
    )


def personalize(bundle: CoverLetterBundle, full_name: str) -> CoverLetterBundle:
    """Swap the {{NAME}} placeholder for the real name. Runs locally, after the LLM call."""
    return CoverLetterBundle(
        **{k: v.replace(NAME_PLACEHOLDER, full_name) for k, v in bundle.as_dict().items()}
    )
