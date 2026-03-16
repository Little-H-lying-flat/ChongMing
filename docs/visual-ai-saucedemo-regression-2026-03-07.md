# SauceDemo visual AI regression report (2026-03-07)

## Summary
- Run at: `2026-03-07T10:07:07.541660+00:00`
- Site: `https://www.saucedemo.com/`
- Overall success: `True`
- Atomic steps passed: `12/12`
- Acceptance groups passed: `5/5`
- Data consistency mismatches: `0`

## Acceptance groups
### 1. User login
- Passed: `True`
- Acceptance: Reach inventory page and show Swag Labs logo plus cart icon.
- Observed page state: `{'page_url': 'https://www.saucedemo.com/inventory.html', 'logo_text': 'Swag Labs', 'cart_count': 1}`
- Notes: all atomic steps and business assertion were aligned
### 2. Add product
- Passed: `True`
- Acceptance: Backpack add button changes to remove and cart badge becomes 1.
- Observed page state: `{'remove_button_count': 1, 'cart_badge_text': '1', 'active_remove_buttons': ['remove-sauce-labs-backpack']}`
- Notes: all atomic steps and business assertion were aligned
### 3. View cart
- Passed: `True`
- Acceptance: Cart page contains Sauce Labs Backpack.
- Observed page state: `{'page_url': 'https://www.saucedemo.com/cart.html', 'item_names': ['Sauce Labs Backpack']}`
- Notes: all atomic steps and business assertion were aligned
### 4. Fill checkout information
- Passed: `True`
- Acceptance: Move to overview page and display order summary with total.
- Observed page state: `{'page_url': 'https://www.saucedemo.com/checkout-step-two.html', 'cart_item_count': 1, 'summary_total_label': 'Total: $32.39'}`
- Notes: all atomic steps and business assertion were aligned
### 5. Finish order
- Passed: `True`
- Acceptance: Display the thank-you confirmation message.
- Observed page state: `{'page_url': 'https://www.saucedemo.com/checkout-complete.html', 'complete_header': 'Thank you for your order!'}`
- Notes: all atomic steps and business assertion were aligned

## Atomic step review
| Step | Engine success | Observation pass | Consistent | Action | Notes |
| --- | --- | --- | --- | --- | --- |
| `open_login_page` | `True` | `True` | `True` | `navigate` | engine result matches observed page state |
| `type_username` | `True` | `True` | `True` | `type` | engine result matches observed page state |
| `type_password` | `True` | `True` | `True` | `type` | engine result matches observed page state |
| `click_login` | `True` | `True` | `True` | `click` | engine result matches observed page state |
| `add_backpack` | `True` | `True` | `True` | `click` | engine result matches observed page state |
| `open_cart` | `True` | `True` | `True` | `click` | engine result matches observed page state |
| `click_checkout` | `True` | `True` | `True` | `click` | engine result matches observed page state |
| `type_first_name` | `True` | `True` | `True` | `type` | engine result matches observed page state |
| `type_last_name` | `True` | `True` | `True` | `type` | engine result matches observed page state |
| `type_postal_code` | `True` | `True` | `True` | `type` | engine result matches observed page state |
| `click_continue` | `True` | `True` | `True` | `click` | engine result matches observed page state |
| `click_finish` | `True` | `True` | `True` | `click` | engine result matches observed page state |

## Findings
- The end-to-end checkout scenario completed successfully on the real site.
- All atomic engine results matched the observed page state.

## Recommendations
- Keep this scripted regression in CI or nightly jobs to detect planner drift on a stable public practice site.
- Capture a lightweight DOM snapshot for each atomic step when a mismatch occurs to speed up diagnosis.
