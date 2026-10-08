"""GET/PUT /api/truth-bank: read and replace data/truth_bank.yaml, validated before saving."""

from datetime import datetime

import yaml
from fastapi import APIRouter, HTTPException

from app.api.deps import SettingsDep
from app.api.schemas import TruthBankDocument, TruthBankUpdate
from app.core.truth_bank import TruthBankError, parse_truth_bank

router = APIRouter(prefix="/truth-bank", tags=["truth bank"])


@router.get("", response_model=TruthBankDocument)
def read_truth_bank(settings: SettingsDep) -> TruthBankDocument:
    path = settings.truth_bank_path
    if not path.is_file():
        raise HTTPException(404, f"No truth bank at {path}")
    text = path.read_text(encoding="utf-8")
    try:
        tb = parse_truth_bank(yaml.safe_load(text))
    except yaml.YAMLError as exc:
        return TruthBankDocument(yaml=text, valid=False, problems=[f"YAML syntax error: {exc}"])
    except TruthBankError as exc:
        return TruthBankDocument(yaml=text, valid=False, problems=exc.problems)
    return TruthBankDocument(yaml=text, valid=True, hash=tb.content_hash())


@router.post("/validate", response_model=TruthBankDocument)
def validate_truth_bank(body: TruthBankUpdate) -> TruthBankDocument:
    """Check YAML without saving it."""
    try:
        tb = parse_truth_bank(yaml.safe_load(body.yaml))
    except yaml.YAMLError as exc:
        return TruthBankDocument(
            yaml=body.yaml, valid=False, problems=[f"YAML syntax error: {exc}"]
        )
    except TruthBankError as exc:
        return TruthBankDocument(yaml=body.yaml, valid=False, problems=exc.problems)
    return TruthBankDocument(yaml=body.yaml, valid=True, hash=tb.content_hash())


@router.put("", response_model=TruthBankDocument)
def write_truth_bank(body: TruthBankUpdate, settings: SettingsDep) -> TruthBankDocument:
    """Validate, back up the current file to data/backups/, then save. Invalid YAML is rejected
    with the list of problems and nothing is written."""
    try:
        tb = parse_truth_bank(yaml.safe_load(body.yaml))
    except yaml.YAMLError as exc:
        raise HTTPException(422, {"message": "YAML syntax error", "problems": [str(exc)]}) from exc
    except TruthBankError as exc:
        raise HTTPException(
            422, {"message": "Truth bank is invalid", "problems": exc.problems}
        ) from exc
    path = settings.truth_bank_path
    if path.is_file():
        backups = settings.data_dir / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (backups / f"truth_bank-{stamp}.yaml").write_bytes(path.read_bytes())
    path.write_text(body.yaml, encoding="utf-8")
    return TruthBankDocument(yaml=body.yaml, valid=True, hash=tb.content_hash())
