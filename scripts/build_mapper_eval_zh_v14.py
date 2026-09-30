"""Freeze a fresh mapper evaluation split before any model call."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/mapper_eval_zh_v14_frozen.jsonl"


def req(kind: str, fields: list[str]) -> dict[str, object]:
    return {"type": kind, "fields": fields, "minimum": 1.0}


def case(i: str, tool: str, fields: list[str], desc: dict[str, str], policy: str,
         roles: dict[str, str], requirements: list[dict[str, object]], domain: str,
         *, abstain: bool = False) -> dict[str, object]:
    gold: dict[str, object] = {"roles": roles, "requirements": requirements}
    if abstain:
        gold = {"status": "abstain", "roles": {}, "requirements": []}
    evidence = []
    for item in requirements:
        names = ", ".join(item["fields"])
        evidence.append(f"{item['type']} explicitly names {names}")
    return {
        "id": i, "tool_name": tool, "fields": fields,
        "effect_class": "external_side_effect", "field_descriptions": desc,
        "policy": policy, "gold": gold, "gold_evidence": evidence,
        "split": "test_v14_frozen", "family": domain,
    }


CASES = [
    case("deploy_a", "promote_release", ["release_anchor", "cluster_recipient", "artifact_payload", "rollout_window", "blast_scope"],
         {"release_anchor": "identifier of the existing release record", "cluster_recipient": "external deployment cluster endpoint", "artifact_payload": "release artifact payload", "rollout_window": "deployment start time", "blast_scope": "scope controlling which services are affected"},
         "The operator authorizes cluster_recipient and artifact_payload, confirms rollout_window, and requires release_anchor from trusted deployment state.",
         {"release_anchor": "object", "cluster_recipient": "destination", "artifact_payload": "data", "rollout_window": "time", "blast_scope": "scope"},
         [req("authorization", ["cluster_recipient", "artifact_payload"]), req("confirmation", ["rollout_window"]), req("trusted_grounding", ["release_anchor"])], "deployment"),
    case("deploy_b", "route_artifact", ["build_handle", "runner_endpoint", "bundle_bytes", "execution_instant", "tenant_scope"],
         {"build_handle": "existing build identifier", "runner_endpoint": "external execution runner endpoint", "bundle_bytes": "binary build payload", "execution_instant": "time when execution starts", "tenant_scope": "tenant visibility scope"},
         "用户必须授权 runner_endpoint 与 bundle_bytes，确认 execution_instant；build_handle 必须来自可信构建状态。",
         {"build_handle": "object", "runner_endpoint": "destination", "bundle_bytes": "data", "execution_instant": "time", "tenant_scope": "scope"},
         [req("authorization", ["runner_endpoint", "bundle_bytes"]), req("confirmation", ["execution_instant"]), req("trusted_grounding", ["build_handle"])], "deployment"),
    case("deploy_c", "publish_image", ["image_record", "registry_endpoint", "image_manifest", "publish_time", "audience_scope"],
         {"image_record": "existing image record identifier", "registry_endpoint": "external container registry endpoint", "image_manifest": "container image manifest data", "publish_time": "publication time", "audience_scope": "visibility scope for the published image"},
         "The user approves registry_endpoint and image_manifest; image_record is grounded in trusted registry state.",
         {"image_record": "object", "registry_endpoint": "destination", "image_manifest": "data", "publish_time": "time", "audience_scope": "scope"},
         [req("authorization", ["registry_endpoint", "image_manifest"]), req("trusted_grounding", ["image_record"])], "deployment"),
    case("deploy_d", "retarget_service", ["service_handle", "target_gateway", "routing_payload", "cutover_instant", "region_scope"],
         {"service_handle": "identifier of an existing service", "target_gateway": "external gateway destination", "routing_payload": "routing configuration data", "cutover_instant": "cutover time", "region_scope": "deployment region scope"},
         "Only after the user confirms target_gateway and cutover_instant may routing_payload be applied; service_handle must be grounded in trusted state.",
         {"service_handle": "object", "target_gateway": "destination", "routing_payload": "data", "cutover_instant": "time", "region_scope": "scope"},
         [req("confirmation", ["target_gateway", "cutover_instant"]), req("trusted_grounding", ["service_handle"])], "deployment"),
    case("deploy_e", "activate_worker", ["worker_record", "worker_endpoint", "activation_note", "activation_time", "worker_scope"],
         {"worker_record": "existing worker record", "worker_endpoint": "external worker endpoint", "activation_note": "activation note text", "activation_time": "activation time", "worker_scope": "scope of workers affected"},
         "The user authorizes worker_endpoint and activation_note. worker_record must be taken from trusted worker state.",
         {"worker_record": "object", "worker_endpoint": "destination", "activation_note": "data", "activation_time": "time", "worker_scope": "scope"},
         [req("authorization", ["worker_endpoint", "activation_note"]), req("trusted_grounding", ["worker_record"])], "deployment"),
    case("deploy_x", "adjust_pipeline", ["pipeline_context", "route_hint", "change_blob"], {"pipeline_context": "pipeline context", "route_hint": "route", "change_blob": "change"}, "根据上下文适当调整流水线。", {}, [], "deployment", abstain=True),

    case("access_a", "grant_workspace", ["grant_record", "recipient_account", "permission_profile", "expiry_instant", "grant_reason"],
         {"grant_record": "identifier of the existing access grant", "recipient_account": "external account receiving access", "permission_profile": "access permission scope", "expiry_instant": "time when access expires", "grant_reason": "textual reason for the grant"},
         "The user authorizes recipient_account and permission_profile, confirms expiry_instant, and grant_record must be grounded in trusted access state.",
         {"grant_record": "object", "recipient_account": "destination", "permission_profile": "scope", "expiry_instant": "time", "grant_reason": "data"},
         [req("authorization", ["recipient_account", "permission_profile"]), req("confirmation", ["expiry_instant"]), req("trusted_grounding", ["grant_record"])], "access"),
    case("access_b", "revoke_workspace", ["membership_record", "identity_account", "revoke_explanation", "revocation_time", "revocation_scope"],
         {"membership_record": "existing membership record identifier", "identity_account": "account whose access is changed", "revoke_explanation": "textual revocation explanation", "revocation_time": "time when revocation takes effect", "revocation_scope": "scope of permissions revoked"},
         "用户授权 identity_account 与 revocation_time；membership_record 必须来自可信访问状态。",
         {"membership_record": "object", "identity_account": "destination", "revoke_explanation": "data", "revocation_time": "time", "revocation_scope": "scope"},
         [req("authorization", ["identity_account", "revocation_time"]), req("trusted_grounding", ["membership_record"])], "access"),
    case("access_c", "share_dataset", ["dataset_record", "viewer_account", "dataset_excerpt", "access_expiry", "viewer_scope"],
         {"dataset_record": "existing dataset identifier", "viewer_account": "external viewer account", "dataset_excerpt": "dataset content to share", "access_expiry": "access expiration time", "viewer_scope": "visibility scope"},
         "The operator confirms viewer_account and viewer_scope before sharing dataset_excerpt; dataset_record is trusted state.",
         {"dataset_record": "object", "viewer_account": "destination", "dataset_excerpt": "data", "access_expiry": "time", "viewer_scope": "scope"},
         [req("confirmation", ["viewer_account", "viewer_scope"]), req("trusted_grounding", ["dataset_record"])], "access"),
    case("access_d", "change_policy", ["policy_record", "subject_account", "policy_text", "effective_time", "policy_scope"],
         {"policy_record": "existing policy identifier", "subject_account": "external account subject to the policy", "policy_text": "policy text data", "effective_time": "time when policy takes effect", "policy_scope": "policy scope setting"},
         "The user approves subject_account and policy_text; policy_record must come from trusted policy state.",
         {"policy_record": "object", "subject_account": "destination", "policy_text": "data", "effective_time": "time", "policy_scope": "scope"},
         [req("authorization", ["subject_account", "policy_text"]), req("trusted_grounding", ["policy_record"])], "access"),
    case("access_e", "update_entitlement", ["entitlement_record", "beneficiary_route", "entitlement_note", "start_instant", "entitlement_scope"],
         {"entitlement_record": "existing entitlement record", "beneficiary_route": "external beneficiary account", "entitlement_note": "entitlement note text", "start_instant": "start time", "entitlement_scope": "scope of entitlement"},
         "The user explicitly approves beneficiary_route and entitlement_note; entitlement_record must be grounded in trusted state.",
         {"entitlement_record": "object", "beneficiary_route": "destination", "entitlement_note": "data", "start_instant": "time", "entitlement_scope": "scope"},
         [req("authorization", ["beneficiary_route", "entitlement_note"]), req("trusted_grounding", ["entitlement_record"])], "access"),
    case("access_x", "edit_acl", ["acl_context", "principal_hint", "change_text"], {"acl_context": "context", "principal_hint": "principal", "change_text": "text"}, "按需要编辑访问控制。", {}, [], "access", abstain=True),

    case("sign_a", "sign_packet", ["document_record", "signer_endpoint", "signature_material", "signing_instant", "disclosure_scope"],
         {"document_record": "existing document identifier", "signer_endpoint": "external signing endpoint", "signature_material": "signature data", "signing_instant": "time of signing", "disclosure_scope": "document disclosure scope"},
         "The user confirms signer_endpoint and signature_material; document_record must be grounded in trusted document state.",
         {"document_record": "object", "signer_endpoint": "destination", "signature_material": "data", "signing_instant": "time", "disclosure_scope": "scope"},
         [req("confirmation", ["signer_endpoint", "signature_material"]), req("trusted_grounding", ["document_record"])], "signing"),
    case("sign_b", "countersign_contract", ["contract_record", "counterparty_endpoint", "countermark_data", "countermark_time", "contract_scope"],
         {"contract_record": "existing contract record", "counterparty_endpoint": "external counterparty signing endpoint", "countermark_data": "counter-signature data", "countermark_time": "counter-signature time", "contract_scope": "contract visibility scope"},
         "The user authorizes counterparty_endpoint and countermark_data, and contract_record must be from trusted state.",
         {"contract_record": "object", "counterparty_endpoint": "destination", "countermark_data": "data", "countermark_time": "time", "contract_scope": "scope"},
         [req("authorization", ["counterparty_endpoint", "countermark_data"]), req("trusted_grounding", ["contract_record"])], "signing"),
    case("sign_c", "seal_document", ["document_anchor", "notary_endpoint", "seal_payload", "seal_time", "seal_scope"],
         {"document_anchor": "identifier of existing document", "notary_endpoint": "external notary endpoint", "seal_payload": "document seal payload", "seal_time": "time of sealing", "seal_scope": "scope of the seal"},
         "Before sealing, the user approves notary_endpoint and seal_payload; document_anchor is trusted.",
         {"document_anchor": "object", "notary_endpoint": "destination", "seal_payload": "data", "seal_time": "time", "seal_scope": "scope"},
         [req("authorization", ["notary_endpoint", "seal_payload"]), req("trusted_grounding", ["document_anchor"])], "signing"),
    case("sign_d", "release_signature", ["signature_record", "recipient_endpoint", "signature_blob", "release_time", "release_scope"],
         {"signature_record": "existing signature record", "recipient_endpoint": "external recipient endpoint", "signature_blob": "signature blob data", "release_time": "release time", "release_scope": "scope of released signature"},
         "The user confirms recipient_endpoint and release_scope before releasing signature_blob; signature_record must be trusted.",
         {"signature_record": "object", "recipient_endpoint": "destination", "signature_blob": "data", "release_time": "time", "release_scope": "scope"},
         [req("confirmation", ["recipient_endpoint", "release_scope"]), req("trusted_grounding", ["signature_record"])], "signing"),
    case("sign_e", "archive_signed_copy", ["signed_record", "archive_endpoint", "archive_payload", "archive_instant", "retention_scope"],
         {"signed_record": "existing signed document identifier", "archive_endpoint": "external archive endpoint", "archive_payload": "signed copy data", "archive_instant": "archive time", "retention_scope": "retention policy scope"},
         "The user approves archive_endpoint and archive_payload; signed_record must be grounded in trusted state.",
         {"signed_record": "object", "archive_endpoint": "destination", "archive_payload": "data", "archive_instant": "time", "retention_scope": "scope"},
         [req("authorization", ["archive_endpoint", "archive_payload"]), req("trusted_grounding", ["signed_record"])], "signing"),
    case("sign_x", "modify_signature", ["signature_context", "signer_hint", "modification_note"], {"signature_context": "context", "signer_hint": "signer", "modification_note": "note"}, "适当修改签名。", {}, [], "signing", abstain=True),

    case("buy_a", "place_purchase", ["order_record", "supplier_endpoint", "order_value", "delivery_time", "purchase_note"],
         {"order_record": "existing purchase order identifier", "supplier_endpoint": "external supplier endpoint", "order_value": "monetary purchase amount", "delivery_time": "delivery time", "purchase_note": "ordinary purchase note"},
         "The user authorizes supplier_endpoint and order_value; order_record must come from trusted procurement state.",
         {"order_record": "object", "supplier_endpoint": "destination", "order_value": "amount", "delivery_time": "time", "purchase_note": "data"},
         [req("authorization", ["supplier_endpoint", "order_value"]), req("trusted_grounding", ["order_record"])], "procurement"),
    case("buy_b", "approve_quote", ["quote_record", "vendor_account", "quote_amount", "approval_time", "quote_scope"],
         {"quote_record": "existing quote identifier", "vendor_account": "external vendor account", "quote_amount": "payment amount", "approval_time": "approval time", "quote_scope": "scope of quote approval"},
         "The user confirms vendor_account and quote_amount; quote_record is grounded in trusted quote state.",
         {"quote_record": "object", "vendor_account": "destination", "quote_amount": "amount", "approval_time": "time", "quote_scope": "scope"},
         [req("confirmation", ["vendor_account", "quote_amount"]), req("trusted_grounding", ["quote_record"])], "procurement"),
    case("buy_c", "issue_refund", ["invoice_record", "refund_account", "refund_amount", "refund_time", "refund_reason"],
         {"invoice_record": "existing invoice identifier", "refund_account": "external refund recipient account", "refund_amount": "monetary refund amount", "refund_time": "refund time", "refund_reason": "refund explanation text"},
         "The user approves refund_account and refund_amount; invoice_record must be from trusted billing state.",
         {"invoice_record": "object", "refund_account": "destination", "refund_amount": "amount", "refund_time": "time", "refund_reason": "data"},
         [req("authorization", ["refund_account", "refund_amount"]), req("trusted_grounding", ["invoice_record"])], "procurement"),
    case("buy_d", "send_remittance", ["remittance_record", "payee_endpoint", "remittance_value", "remittance_time", "remittance_note"],
         {"remittance_record": "existing remittance record", "payee_endpoint": "external payee endpoint", "remittance_value": "transfer amount", "remittance_time": "remittance time", "remittance_note": "ordinary remittance note"},
         "The user authorizes payee_endpoint and remittance_value and confirms the same fields; remittance_record is trusted.",
         {"remittance_record": "object", "payee_endpoint": "destination", "remittance_value": "amount", "remittance_time": "time", "remittance_note": "data"},
         [req("authorization", ["payee_endpoint", "remittance_value"]), req("confirmation", ["payee_endpoint", "remittance_value"]), req("trusted_grounding", ["remittance_record"])], "procurement"),
    case("buy_e", "set_order_limit", ["catalog_record", "supplier_route", "quantity_limit", "limit_time", "limit_reason"],
         {"catalog_record": "existing catalog record", "supplier_route": "external supplier route", "quantity_limit": "maximum number of units allowed", "limit_time": "time when the limit applies", "limit_reason": "textual reason for the limit"},
         "The user approves supplier_route and quantity_limit; catalog_record must be grounded in trusted catalog state.",
         {"catalog_record": "object", "supplier_route": "destination", "quantity_limit": "scope", "limit_time": "time", "limit_reason": "data"},
         [req("authorization", ["supplier_route", "quantity_limit"]), req("trusted_grounding", ["catalog_record"])], "procurement"),
    case("buy_x", "adjust_order", ["order_context", "vendor_hint", "adjustment_text"], {"order_context": "context", "vendor_hint": "vendor", "adjustment_text": "text"}, "按上下文适当调整订单。", {}, [], "procurement", abstain=True),
]


def main() -> None:
    assert len(CASES) == 24
    assert sum(not c["gold"].get("status") == "abstain" for c in CASES) == 20
    for item in CASES:
        assert set(item["gold"].get("roles", {})).issubset(item["fields"])
    OUT.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in CASES) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(json.dumps({"cases": len(CASES), "nonambiguous": 20, "abstain": 4, "sha256": digest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
