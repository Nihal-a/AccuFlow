# COMPLETE END-TO-END VALIDATION: SaaS Workflow - Client A Full Cycle

## PRECONDITIONS
1. Fresh DB: `python manage.py migrate && python manage.py createsuperuser`
2. Launch the server: `python manage.py runserver`
3. Since Client/Supplier isolation relies on the `Clients` model and `UserAccount`, make sure to create a test user (Client A) with `is_client=True` and a corresponding `Clients` configuration.

## INITIAL SETUP (Admin)
- Login as Admin.
- Navigate to Clients / Users and create **Client A** (username: `testclient1`, password: `test123`).
- Ensure the client has an associated active entry in `Clients` table with an active subscription.
- Create at least one **Godown** for Client A (e.g., "Main Warehouse") as Purchases and Sales require a Godown to store inventory.

## STEP 1: SUPPLIER CRUD (as Client A)
- [ ] **Login:** Navigate to `/login/` -> login as `testclient1` / `test123`.
- [ ] **Create Supplier:** Go to `/suppliers/create/`.
  - Provide Name: "Acme Corp", Phone: "0501234567", Address: "Dubai". 
  - Save.
- [ ] **Verify List:** Go to `/suppliers/` and check that "Acme Corp" is listed.
- [ ] **Edit Supplier:** Click edit on "Acme Corp" (goes to `/suppliers/edit/<id>/`). 
  - Change phone number. Save. 
  - Verify phone number is updated.
- [ ] **View Supplier:** Click to view the details (`/suppliers/view/<id>/`) and confirm all fields are correct.
- [ ] **Delete Supplier:** Create a dummy supplier "To Be Deleted", go to `/suppliers/delete/<id>/` (or click the delete button). Confirm it is soft-deleted (no longer shows up in `/suppliers/`).

## STEP 2: CUSTOMER CRUD
- [ ] **Create Customer:** Navigate to `/customers/create/`. Provide Name: "Ahmed Corp", Address: "Abu Dhabi". Save.
- [ ] **Verify List:** Go to `/customers/` and ensure it's listed.
- [ ] **Edit/View/Delete:** Similarly test creating a dummy, editing, viewing, and soft-deleting Customer.

## STEP 3: PURCHASE CYCLE
- [ ] **Navigate to Purchases:** `/purchase/`
- [ ] **Create Purchase:** 
  - The UI likely uses an API first for holding (`/purchase/api/hold_purchase/`) and then final form submit (`/purchase/create/`). 
  - Select Supplier: "Acme Corp" (Supplier ID).
  - Select Godown: "Main Warehouse".
  - Qty: 100, Rate/Amount: 10 AED. (Total amount = 1000).
  - Save the purchase.
- [ ] **CRITICAL BALANCE CHECK:**
  - Go to `/suppliers/` or `/supplierledger/`. 
  - Verify "Acme Corp" Balance INCREASES by 1000 AED as a Credit (meaning we owe them 1000).
  - Verify "Main Warehouse" stock for this item increases by 100.
  - Check Supplier Ledger (`/supplierledger/`) to ensure the 1000 AED entry exists as `PR` (Purchase).

## STEP 4: SALE CYCLE
- [ ] **Navigate to Sales:** `/sale/`
- [ ] **Create Sale:**
  - Select Customer: "Ahmed Corp" (Customer ID).
  - Select Godown: "Main Warehouse".
  - Qty: 80, Rate/Amount: 15 AED. (Total = 1200 AED).
  - Save the sale.
- [ ] **CRITICAL BALANCE CHECK:**
  - Go to `/customers/` or `/customerledger/`. 
  - Verify "Ahmed Corp" Balance INCREASES by 1200 AED as a Debit (meaning they owe us 1200).
  - Net balance: +200 AED, Ledger shows both entries.
  - Verify "Main Warehouse" stock decreases by 80.
  - Check Customer Ledger (`/customerledger/`) to ensure the 1200 AED entry is recorded under `SL` (Sale).

## STEP 5: BALANCE INTEGRITY CHECKS
- [ ] **Delete Sale:** Go to `/sale/` and delete the recent Sale of 80 Qty. 
  - **Expected:** "Ahmed Corp" debit balance should revert/decrease by 1200. Godown stock recovers by 80.
- [ ] **Recreate/Edit:** Recreate the sale via `/sale/` but set Qty to 50 instead of 80.
  - **Expected:** "Ahmed Corp" debit should reflect 50 * 15 = 750 AED. Godown stock recovers by 30 net.

## STEP 6: EDGE CASES (Critical Testing focus)
- [ ] **Negative Stock Validation:** Try to sell more than available in Godown (e.g., sell 200). System should ideally prevent or handle it. 
- [ ] **Client Isolation (Data Leaks):** Login as a different Client (Client B). Navigate to `/customers/` or `/supplierledger/`. You MUST NOT see "Acme Corp" or "Ahmed Corp".
- [ ] **Soft Delete Integrity:** Deleting a Supplier who has existing Purchases. Ensure the system handles this gracefully.
- [ ] **Credit/Debit Balance Limit:** Verify balances cannot be manipulated below zero if they represent credit or debit limits.

## STEP 7: ADMIN PERSPECTIVE
- [ ] **Login as Admin.**
- [ ] **Dashboard Check:** Make sure Admin views are accurate.
- [ ] **Toggle Features:** If possible, edit Client A's subscription to "Inactive" and verify Client A is immediately locked out of workflows (`subscription_expired` redirect) within 7 days or immediate.
