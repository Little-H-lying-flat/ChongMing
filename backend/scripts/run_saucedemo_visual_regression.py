import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.engines.right_pupil import RightPupilEngine


OUTPUT_JSON = BACKEND_DIR / "tmp_visual_ai_eval_saucedemo_checkout_regression_2026-03-07.json"
OUTPUT_MD = PROJECT_DIR / "docs" / "visual-ai-saucedemo-regression-2026-03-07.md"

BASE_URL = "https://www.saucedemo.com/"
USERNAME = "standard_user"
PASSWORD = "secret_sauce"
FIRST_NAME = "Codex"
LAST_NAME = "Regression"
POSTAL_CODE = "200000"


@dataclass(frozen=True)
class AtomicStep:
    step_id: str
    group_id: str
    description: str
    url: str | None
    verifier: Callable[[Any], Awaitable[dict[str, Any]]]


async def safe_input_value(page: Any, selector: str) -> str:
    locator = page.locator(selector)
    count = await locator.count()
    if count == 0:
        return ""
    return await locator.first.input_value()


async def safe_text(page: Any, selector: str) -> str:
    locator = page.locator(selector)
    count = await locator.count()
    if count == 0:
        return ""
    text = await locator.first.text_content()
    return (text or "").strip()


async def safe_count(page: Any, selector: str) -> int:
    return await page.locator(selector).count()


async def wait_for_settle(page: Any) -> None:
    for state in ("domcontentloaded", "networkidle"):
        try:
            await page.wait_for_load_state(state, timeout=3000)
        except Exception:
            continue
    await page.wait_for_timeout(600)


def normalize_engine_result(result: dict[str, Any]) -> dict[str, Any]:
    screenshot_before = result.get("screenshot_before")
    screenshot_after = result.get("screenshot_after")
    return {
        "success": bool(result.get("success")),
        "action_taken": result.get("action_taken"),
        "target_description": result.get("target_description"),
        "page_url": result.get("page_url"),
        "page_title": result.get("page_title"),
        "strategy": result.get("strategy"),
        "error": result.get("error"),
        "screenshot_before_len": len(screenshot_before) if isinstance(screenshot_before, str) else 0,
        "screenshot_after_len": len(screenshot_after) if isinstance(screenshot_after, str) else 0,
    }


def assess_consistency(engine_success: bool, observation_passed: bool) -> dict[str, Any]:
    consistent = engine_success == observation_passed
    if consistent:
        reason = "engine result matches observed page state"
    elif engine_success and not observation_passed:
        reason = "engine reported success but page state did not satisfy the expected assertion"
    else:
        reason = "engine reported failure but the expected page state was still observed"
    return {"consistent": consistent, "reason": reason}


async def verify_open_login(page: Any) -> dict[str, Any]:
    username_value = await safe_input_value(page, "[data-test='username']")
    password_exists = await safe_count(page, "[data-test='password']")
    return {
        "passed": page.url.startswith(BASE_URL) and password_exists > 0,
        "details": {
            "page_url": page.url,
            "page_title": await page.title(),
            "username_value": username_value,
            "password_input_count": password_exists,
        },
    }


async def verify_username(page: Any) -> dict[str, Any]:
    value = await safe_input_value(page, "[data-test='username']")
    return {"passed": value == USERNAME, "details": {"username_value": value}}


async def verify_password(page: Any) -> dict[str, Any]:
    value = await safe_input_value(page, "[data-test='password']")
    return {"passed": value == PASSWORD, "details": {"password_length": len(value)}}


async def verify_login_click(page: Any) -> dict[str, Any]:
    logo_text = await safe_text(page, ".app_logo")
    cart_count = await safe_count(page, ".shopping_cart_link")
    inventory_count = await safe_count(page, ".inventory_list")
    return {
        "passed": (
            "/inventory.html" in page.url
            and logo_text == "Swag Labs"
            and cart_count > 0
            and inventory_count > 0
        ),
        "details": {
            "page_url": page.url,
            "logo_text": logo_text,
            "cart_count": cart_count,
            "inventory_list_count": inventory_count,
        },
    }


async def verify_add_backpack(page: Any) -> dict[str, Any]:
    remove_count = await safe_count(page, "[data-test='remove-sauce-labs-backpack']")
    badge_text = await safe_text(page, ".shopping_cart_badge")
    active_remove_buttons = await page.locator("[data-test^='remove-']").evaluate_all(
        "(elements) => elements.map((element) => element.getAttribute('data-test'))"
    )
    return {
        "passed": remove_count > 0 and badge_text == "1",
        "details": {
            "remove_button_count": remove_count,
            "cart_badge_text": badge_text,
            "active_remove_buttons": active_remove_buttons,
        },
    }


async def verify_open_cart(page: Any) -> dict[str, Any]:
    item_names = await page.locator(".inventory_item_name").all_text_contents()
    normalized_names = [name.strip() for name in item_names]
    return {
        "passed": "/cart.html" in page.url and "Sauce Labs Backpack" in normalized_names,
        "details": {
            "page_url": page.url,
            "item_names": normalized_names,
        },
    }


async def verify_click_checkout(page: Any) -> dict[str, Any]:
    first_name_count = await safe_count(page, "[data-test='firstName']")
    return {
        "passed": "/checkout-step-one.html" in page.url and first_name_count > 0,
        "details": {
            "page_url": page.url,
            "first_name_input_count": first_name_count,
        },
    }


async def verify_first_name(page: Any) -> dict[str, Any]:
    value = await safe_input_value(page, "[data-test='firstName']")
    return {"passed": value == FIRST_NAME, "details": {"first_name_value": value}}


async def verify_last_name(page: Any) -> dict[str, Any]:
    value = await safe_input_value(page, "[data-test='lastName']")
    return {"passed": value == LAST_NAME, "details": {"last_name_value": value}}


async def verify_postal_code(page: Any) -> dict[str, Any]:
    value = await safe_input_value(page, "[data-test='postalCode']")
    return {"passed": value == POSTAL_CODE, "details": {"postal_code_value": value}}


async def verify_continue(page: Any) -> dict[str, Any]:
    summary_total = await safe_text(page, ".summary_total_label")
    cart_items = await page.locator(".cart_item").count()
    return {
        "passed": "/checkout-step-two.html" in page.url and cart_items > 0 and "Total:" in summary_total,
        "details": {
            "page_url": page.url,
            "cart_item_count": cart_items,
            "summary_total_label": summary_total,
        },
    }


async def verify_finish(page: Any) -> dict[str, Any]:
    complete_text = await safe_text(page, ".complete-header")
    return {
        "passed": "/checkout-complete.html" in page.url and complete_text == "Thank you for your order!",
        "details": {
            "page_url": page.url,
            "complete_header": complete_text,
        },
    }


async def verify_group_login(page: Any) -> dict[str, Any]:
    logo_text = await safe_text(page, ".app_logo")
    cart_count = await safe_count(page, ".shopping_cart_link")
    return {
        "passed": "/inventory.html" in page.url and logo_text == "Swag Labs" and cart_count > 0,
        "details": {
            "page_url": page.url,
            "logo_text": logo_text,
            "cart_count": cart_count,
        },
    }


async def verify_group_add_item(page: Any) -> dict[str, Any]:
    return await verify_add_backpack(page)


async def verify_group_view_cart(page: Any) -> dict[str, Any]:
    return await verify_open_cart(page)


async def verify_group_checkout(page: Any) -> dict[str, Any]:
    return await verify_continue(page)


async def verify_group_finish(page: Any) -> dict[str, Any]:
    return await verify_finish(page)


ATOMIC_STEPS: list[AtomicStep] = [
    AtomicStep("open_login_page", "login", "Open the SauceDemo login page", BASE_URL, verify_open_login),
    AtomicStep("type_username", "login", f"Type {USERNAME} into the username input", None, verify_username),
    AtomicStep("type_password", "login", f"Type {PASSWORD} into the password input", None, verify_password),
    AtomicStep("click_login", "login", "Click the Login button", None, verify_login_click),
    AtomicStep("add_backpack", "add_item", "Click Add to cart for Sauce Labs Backpack", None, verify_add_backpack),
    AtomicStep("open_cart", "view_cart", "Open the shopping cart", None, verify_open_cart),
    AtomicStep("click_checkout", "checkout_info", "Click the Checkout button", None, verify_click_checkout),
    AtomicStep("type_first_name", "checkout_info", f"Type {FIRST_NAME} into the First Name input", None, verify_first_name),
    AtomicStep("type_last_name", "checkout_info", f"Type {LAST_NAME} into the Last Name input", None, verify_last_name),
    AtomicStep("type_postal_code", "checkout_info", f"Type {POSTAL_CODE} into the Postal Code input", None, verify_postal_code),
    AtomicStep("click_continue", "checkout_info", "Click Continue to go to the checkout overview page", None, verify_continue),
    AtomicStep("click_finish", "finish_order", "Click Finish to submit and complete the order", None, verify_finish),
]


GROUP_ORDER = [
    {
        "group_id": "login",
        "name": "1. User login",
        "acceptance": "Reach inventory page and show Swag Labs logo plus cart icon.",
        "verifier": verify_group_login,
        "terminal_step_id": "click_login",
    },
    {
        "group_id": "add_item",
        "name": "2. Add product",
        "acceptance": "Backpack add button changes to remove and cart badge becomes 1.",
        "verifier": verify_group_add_item,
        "terminal_step_id": "add_backpack",
    },
    {
        "group_id": "view_cart",
        "name": "3. View cart",
        "acceptance": "Cart page contains Sauce Labs Backpack.",
        "verifier": verify_group_view_cart,
        "terminal_step_id": "open_cart",
    },
    {
        "group_id": "checkout_info",
        "name": "4. Fill checkout information",
        "acceptance": "Move to overview page and display order summary with total.",
        "verifier": verify_group_checkout,
        "terminal_step_id": "click_continue",
    },
    {
        "group_id": "finish_order",
        "name": "5. Finish order",
        "acceptance": "Display the thank-you confirmation message.",
        "verifier": verify_group_finish,
        "terminal_step_id": "click_finish",
    },
]


def build_report(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# SauceDemo visual AI regression report (2026-03-07)")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Run at: `{data['run_at']}`")
    lines.append(f"- Site: `{data['site']}`")
    lines.append(f"- Overall success: `{data['overall_success']}`")
    lines.append(f"- Atomic steps passed: `{data['summary']['atomic_passed']}/{data['summary']['atomic_total']}`")
    lines.append(f"- Acceptance groups passed: `{data['summary']['group_passed']}/{data['summary']['group_total']}`")
    lines.append(f"- Data consistency mismatches: `{data['summary']['consistency_mismatches']}`")
    lines.append("")
    lines.append("## Acceptance groups")
    for group in data["group_results"]:
        lines.append(f"### {group['name']}")
        lines.append(f"- Passed: `{group['passed']}`")
        lines.append(f"- Acceptance: {group['acceptance']}")
        lines.append(f"- Observed page state: `{group['observation']}`")
        lines.append(f"- Notes: {group['notes']}")
    lines.append("")
    lines.append("## Atomic step review")
    lines.append("| Step | Engine success | Observation pass | Consistent | Action | Notes |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for step in data["atomic_results"]:
        lines.append(
            f"| `{step['step_id']}` | `{step['engine_result']['success']}` | "
            f"`{step['observation']['passed']}` | `{step['consistency']['consistent']}` | "
            f"`{step['engine_result']['action_taken']}` | {step['consistency']['reason']} |"
        )
    lines.append("")
    lines.append("## Findings")
    for item in data["findings"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Recommendations")
    for item in data["recommendations"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


async def main() -> None:
    engine = RightPupilEngine()
    atomic_results: list[dict[str, Any]] = []
    group_results: list[dict[str, Any]] = []
    findings: list[str] = []
    recommendations: list[str] = []
    stopped_early = False

    try:
        await engine.start_session(headless=True)
        page = engine.page
        assert page is not None

        for atomic_step in ATOMIC_STEPS:
            raw_result = await engine.execute_step(
                description=atomic_step.description,
                url=atomic_step.url or "",
                execution_id="saucedemo-regression-2026-03-07",
            )
            await wait_for_settle(page)
            observation = await atomic_step.verifier(page)
            engine_result = normalize_engine_result(raw_result)
            consistency = assess_consistency(engine_result["success"], observation["passed"])

            atomic_results.append(
                {
                    "step_id": atomic_step.step_id,
                    "group_id": atomic_step.group_id,
                    "description": atomic_step.description,
                    "engine_result": engine_result,
                    "observation": observation,
                    "consistency": consistency,
                }
            )

            if not consistency["consistent"]:
                findings.append(
                    f"Atomic step {atomic_step.step_id} had a mismatch between engine success and observed page state."
                )
            if not observation["passed"]:
                findings.append(
                    f"Atomic step {atomic_step.step_id} did not satisfy its expected page assertion."
                )
                if atomic_step.step_id == "add_backpack":
                    active_remove_buttons = observation["details"].get("active_remove_buttons", [])
                    if active_remove_buttons:
                        findings.append(
                            "The planner added the wrong product: "
                            + ", ".join(active_remove_buttons)
                            + " became active instead of remove-sauce-labs-backpack."
                        )
                stopped_early = True

            for group in GROUP_ORDER:
                if group["terminal_step_id"] != atomic_step.step_id:
                    continue
                group_observation = await group["verifier"](page)
                group_atomic = [item for item in atomic_results if item["group_id"] == group["group_id"]]
                mismatches = [item["step_id"] for item in group_atomic if not item["consistency"]["consistent"]]
                notes = "all atomic steps and business assertion were aligned"
                if not group_observation["passed"]:
                    notes = "business acceptance assertion failed"
                elif mismatches:
                    notes = f"business acceptance passed but atomic mismatches were present: {', '.join(mismatches)}"

                group_results.append(
                    {
                        "group_id": group["group_id"],
                        "name": group["name"],
                        "acceptance": group["acceptance"],
                        "passed": group_observation["passed"],
                        "observation": group_observation["details"],
                        "notes": notes,
                        "atomic_step_ids": [item["step_id"] for item in group_atomic],
                    }
                )

                if not group_observation["passed"]:
                    findings.append(f"Acceptance group {group['name']} failed its business assertion.")
                    stopped_early = True

            if stopped_early:
                break

        final_page = {
            "url": page.url,
            "title": await page.title(),
            "thank_you_text": await safe_text(page, ".complete-header"),
            "cart_badge_text": await safe_text(page, ".shopping_cart_badge"),
        }
    finally:
        await engine.stop_session()

    atomic_passed = sum(1 for item in atomic_results if item["observation"]["passed"])
    group_passed = sum(1 for item in group_results if item["passed"])
    mismatch_count = sum(1 for item in atomic_results if not item["consistency"]["consistent"])
    overall_success = bool(group_results) and all(item["passed"] for item in group_results) and not stopped_early

    if overall_success:
        findings.append("The end-to-end checkout scenario completed successfully on the real site.")
    else:
        recommendations.append("Inspect the first failed atomic step and tighten the prompt or self-healing branch for that page state.")
        add_backpack_result = next(
            (item for item in atomic_results if item["step_id"] == "add_backpack"),
            None,
        )
        if add_backpack_result:
            active_remove_buttons = add_backpack_result["observation"]["details"].get("active_remove_buttons", [])
            if active_remove_buttons:
                recommendations.append(
                    "For product-list pages, bind item actions to a nearby title match before clicking an ambiguous Add to cart button."
                )

    if mismatch_count == 0:
        findings.append("All atomic engine results matched the observed page state.")
    else:
        recommendations.append("Add stronger post-action assertions in RightPupil evaluation so success is not reported before the page reaches the intended state.")

    recommendations.append("Keep this scripted regression in CI or nightly jobs to detect planner drift on a stable public practice site.")
    recommendations.append("Capture a lightweight DOM snapshot for each atomic step when a mismatch occurs to speed up diagnosis.")

    data = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "site": BASE_URL,
        "credentials": {"username": USERNAME, "password": PASSWORD},
        "test_data": {
            "first_name": FIRST_NAME,
            "last_name": LAST_NAME,
            "postal_code": POSTAL_CODE,
        },
        "overall_success": overall_success,
        "summary": {
            "atomic_total": len(atomic_results),
            "atomic_passed": atomic_passed,
            "group_total": len(group_results),
            "group_passed": group_passed,
            "consistency_mismatches": mismatch_count,
            "stopped_early": stopped_early,
        },
        "atomic_results": atomic_results,
        "group_results": group_results,
        "final_page": final_page,
        "findings": findings,
        "recommendations": recommendations,
    }

    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(build_report(data), encoding="utf-8")
    print(json.dumps({"json": str(OUTPUT_JSON), "md": str(OUTPUT_MD), "overall_success": overall_success}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
