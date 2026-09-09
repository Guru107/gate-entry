# Gate Entry System - User Guide for Security Guards

## Table of Contents
1. [Introduction](#introduction)
2. [Understanding Gate Passes](#understanding-gate-passes)
3. [Creating a Gate Pass for Incoming Material](#creating-a-gate-pass-for-incoming-material)
4. [Creating a Gate Pass for Outgoing Material](#creating-a-gate-pass-for-outgoing-material)
5. [Handling Material Returns](#handling-material-returns)
6. [Recording Material Discrepancies](#recording-material-discrepancies)
7. [Understanding Compliance Requirements](#understanding-compliance-requirements)
8. [Viewing Reports](#viewing-reports)
9. [Common Scenarios](#common-scenarios)
10. [Troubleshooting](#troubleshooting)

---

## Introduction

Welcome to the Gate Entry System! This system helps you record all material movements in and out of the facility. As a Security Guard, your role is to:

- Create gate passes when materials arrive or leave
- Verify vehicle and driver information
- Record accurate quantities of materials
- Ensure compliance documents are in place before allowing material to leave
- Report any discrepancies or issues with materials

This guide will walk you through all the tasks you need to perform using the system.

---

## Understanding Gate Passes

### What is a Gate Pass?

A Gate Pass is a document that records material movement at the gate. Every time material enters or exits the facility, you need to create a Gate Pass.

### Types of Gate Passes

**Gate In** - Used when material is entering the facility:
- Materials arriving from suppliers (Purchase Orders)
- Materials from subcontractors (Subcontracting Orders)
- Materials returning from external locations (Stock Entries)

**Gate Out** - Used when material is leaving the facility:
- Materials being dispatched to customers (Sales Invoices, Delivery Notes)
- Materials being sent to subcontractors (Stock Entries)
- Materials being transferred to other locations (Stock Entries)

### Gate Pass Status

A Gate Pass goes through different stages:

- **Draft** - You are still entering information
- **Submitted** - The gate pass is complete and recorded
- **Receipt Created** - The material has been processed in the warehouse
- **Cancelled** - The gate pass was cancelled (material did not arrive/leave)

---

## Creating a Gate Pass for Incoming Material

### When to Create a Gate In Pass

Create a Gate In pass when:
- A supplier arrives with materials ordered through a Purchase Order
- A subcontractor delivers finished goods or returns raw materials
- Materials are returning from an external location

### Step-by-Step: Creating a Gate In Pass for Purchase Order

1. **Click "New" to create a new Gate Pass**

2. **Select the Document Type**
   - In the "Document Reference" field, select "Purchase Order"
   - The system will automatically set the Entry Type to "Gate In"

3. **Select the Purchase Order**
   - In the "Reference Number" field, search for and select the Purchase Order number
   - The system will automatically fill in:
     - Supplier name
     - Supplier address
     - Company

4. **Enter Vehicle and Driver Information**
   - **Vehicle Number** (Required): Enter the vehicle registration number
   - **Driver Name** (Required): Enter the driver's full name
   - **Driver Contact Number** (Optional): Enter the driver's phone number

5. **Verify Your Information**
   - Your name should automatically appear in "Security Guard Name"
   - The date and time should be automatically filled
   - If any of these are missing, enter them manually

6. **Add Items That Are Received**
   - Scroll down to the "Items List" section
   - Click the "Add Item" button
   - A dialog will appear showing all available items from the Purchase Order
   - For each item, you will see:
     - Item code and name
     - Ordered quantity (how much was ordered)
     - Pending quantity (how much is still expected)
   - Select the items that are actually received by checking the boxes next to them
   - Click "Add Selected" to add those items to your gate pass
   - The dialog will close and the selected items will appear in the items list

7. **Enter Received Quantities**
   - For each item you added, enter the actual quantity received in the "Received Quantity" field
   - You can:
     - Add more items by clicking the "Add Item" button again
     - Remove items by clicking the "-" icon next to any item
     - View more details by clicking the "i" icon next to any item
   - **Important**: You cannot receive more than the ordered quantity (or pending quantity if some was already received)

8. **Review the Information**
   - Check that all vehicle and driver details are correct
   - Verify that received quantities match what you physically see
   - Ensure all required items are listed

9. **Save the Gate Pass**
   - Click "Save" to save as draft (you can come back to edit it)
   - Or click "Submit" to finalize the gate pass

10. **After Submission**
    - The gate pass status changes to "Submitted"
    - Your job is done. A stores or downstream user will open the submitted Gate Pass and click **"Create Purchase Receipt"** to generate the draft Purchase Receipt(s).
    - You do not need to take any further action — you will not receive a notification for GRN creation.

### Step-by-Step: Creating a Gate In Pass for Purchase Order — Multiple Invoices

When a supplier vehicle carries material against **more than one supplier invoice** (all on the same Purchase Order), use this flow instead of creating a separate Gate Pass per invoice.

1. **Create a new Gate Pass and select the Purchase Order** (steps 1–4 from the single-invoice flow above — Document Reference, PO, supplier details auto-fill, vehicle and driver).

2. **Add the first invoice**
   - In the Items section, click **"Add Invoice"**.
   - Enter the invoice number from the first delivery challan the driver presents.
   - An invoice section (heading = that invoice number) appears. Duplicate invoice numbers on the same gate pass are rejected.

3. **Add items for that invoice**
   - Inside the invoice section, click **"Add Item"**.
   - A dialog shows all PO items with their remaining pending quantity (ordered minus already received, minus quantity already allocated to sibling invoices on this gate pass).
   - Select the items present on this invoice and click **"Add Selected"**.
   - Enter the received quantity for each item (must be greater than zero and within the pending quantity shown).

4. **Repeat for every additional invoice**
   - Click **"Add Invoice"** again, enter the next invoice number, and add its items and quantities.
   - Continue until all invoices the driver has presented are recorded.

5. **Review and submit**
   - Verify vehicle/driver details and all invoice sections.
   - Click **"Submit"**.

6. **After submission**
   - The gate pass status changes to "Submitted". Your job is done.
   - The Gate Pass shows a summary table: **Invoice No → Purchase Receipt → status** for every GRN from this vehicle entry (initially all pending).
   - You do not need to take any further action on the Purchase Receipts.

> **Stores: creating GRNs**
> A stores or downstream user (with Purchase Receipt create permission) opens the submitted Gate Pass and clicks **"Create Purchase Receipt"**. This creates one draft Purchase Receipt for every invoice on the gate pass in a single, all-or-nothing action — if any invoice fails, no receipts are created and a clear error is shown. The button is hidden once all invoices already have a Purchase Receipt.

### Step-by-Step: Creating a Gate In Pass for Subcontracting Order

The process is very similar to Purchase Orders:

1. Select "Subcontracting Order" as the Document Reference
2. Select the Subcontracting Order number
3. Enter vehicle and driver details
4. Click "Add Item" button to select items that are received
5. Select the items from the dialog and click "Add Selected"
6. Enter received quantities for each item
7. Submit the gate pass

After submission, a "Create Subcontracting Receipt" button will appear for the store manager.

### Step-by-Step: Creating a Gate In Pass for Returning Material (Stock Entry)

When material is returning from an external location:

1. Select "Stock Entry" as the Document Reference
2. Select the Stock Entry number (the system will show only return entries)
3. The system will automatically:
   - Set Entry Type to "Gate In"
   - Link to the original outbound transfer
   - Fill in material details
4. Enter vehicle and driver information
5. Verify the material quantities
6. Submit the gate pass

**Special Case: Material Returning Without Stock Entry**

Sometimes material returns before a Stock Entry is created:

1. Select "Stock Entry" as Document Reference
2. Check the box "Returning Against Outbound Transfer"
3. In "Outbound Material Transfer", select the original Stock Entry that sent the material out
4. Enter vehicle and driver details
5. Enter the material quantities manually
6. Submit the gate pass

---

## Creating a Gate Pass for Outgoing Material

### When to Create a Gate Out Pass

Create a Gate Out pass when:
- Material is being dispatched to a customer (Sales Invoice or Delivery Note)
- Material is being sent to a subcontractor (Stock Entry)
- Material is being transferred to another location (Stock Entry)

### Step-by-Step: Creating a Gate Out Pass for Sales Invoice

1. **Click "New" to create a new Gate Pass**

2. **Select the Document Type**
   - In "Document Reference", select "Sales Invoice"
   - The system will automatically set Entry Type to "Gate Out"

3. **Select the Sales Invoice**
   - In "Reference Number", search for and select the Sales Invoice number
   - The system will automatically fill in:
     - Vehicle number (if available in the invoice)
     - Driver name (if available in the invoice)
     - Driver contact (if available in the invoice)
     - Material items with quantities

4. **Verify Vehicle and Driver Information**
   - Check if the vehicle number, driver name, and contact are filled
   - If any are missing, enter them manually
   - **Important**: Vehicle number and driver name are required

5. **Review Material Items**
   - The system automatically shows all items from the Sales Invoice
   - **Important**: You cannot change the quantities - they are locked to match the invoice
   - Review the items to ensure they match what is being dispatched

6. **Check Compliance Status**
   - Look for the compliance status section
   - You will see:
     - E-Invoice status (for Sales Invoices)
     - E-Way Bill status
   - **Critical**: If the invoice value is above the threshold set by your company, you MUST see:
     - E-Invoice: Generated (for Sales Invoices)
     - E-Way Bill: Generated
   - If these are not generated, you will NOT be able to submit the gate pass

7. **Submit the Gate Pass**
   - If compliance documents are missing, the system will show an error
   - Contact the person who created the Sales Invoice to generate the required documents
   - Once compliance documents are generated, you can submit the gate pass

### Step-by-Step: Creating a Gate Out Pass for Delivery Note

The process is similar to Sales Invoice:

1. Select "Delivery Note" as Document Reference
2. Select the Delivery Note number
3. Verify vehicle and driver information
4. Review material items (quantities are locked)
5. Check compliance status (E-Way Bill may be required)
6. Submit the gate pass

**Note**: E-Invoice is not applicable for Delivery Notes, only E-Way Bill may be required.

### Step-by-Step: Creating a Gate Out Pass for Stock Entry

When material is being sent out via Stock Entry:

1. **Select "Stock Entry" as Document Reference**
   - The system will automatically set Entry Type to "Gate Out"

2. **Select the Stock Entry**
   - In "Reference Number", select the Stock Entry
   - The system will show only Material Transfer or Send to Subcontractor entries
   - Material details will be automatically filled

3. **Enter Vehicle and Driver Information**
   - Enter vehicle number (required)
   - Enter driver name (required)
   - Enter driver contact (optional)

4. **Review Material Items**
   - Verify that all items match what is being dispatched
   - Quantities are automatically set from the Stock Entry

5. **Submit the Gate Pass**

**Note**: Some Stock Entries may automatically create a draft gate pass. In that case, you just need to:
- Open the draft gate pass
- Verify and complete the vehicle/driver information
- Submit it

---

## Handling Material Returns

### Understanding Returns

Sometimes material that was sent out needs to come back. This could be:
- Material sent to a subcontractor that is being returned
- Material transferred to another location that is coming back
- Rejected material from a customer

### Creating a Return Gate Pass

1. **Select "Stock Entry" as Document Reference**

2. **Select the Return Stock Entry**
   - The system will show only return entries
   - Entry Type will automatically be set to "Gate In"

3. **Verify the Link to Original Transfer**
   - The system automatically links to the original outbound transfer
   - You can see this in the "Outbound Material Transfer" field

4. **Enter Vehicle and Driver Information**

5. **Verify Material Quantities**
   - The system shows what should be returning
   - Verify against what actually arrived

6. **Submit the Gate Pass**

### Manual Return Flow

If material is returning but no Stock Entry exists yet:

1. Select "Stock Entry" as Document Reference
2. Check "Returning Against Outbound Transfer"
3. Select the original outbound Stock Entry in "Outbound Material Transfer"
4. Enter vehicle and driver details
5. Enter material quantities manually
6. Submit the gate pass

---

## Recording Material Discrepancies

### What are Discrepancies?

Discrepancies occur when:
- Material is lost during transit
- Material arrives damaged
- Material quantity doesn't match what was expected

### How to Record Discrepancies

1. **Open the Gate Pass** (can be draft or submitted)

2. **Go to the Discrepancy Details Section**

3. **Check "Has Discrepancy"**
   - This will enable the discrepancy fields

4. **Enter Lost Quantity**
   - Enter the quantity of material that was lost
   - This should be in the same unit as the material

5. **Enter Damaged Quantity**
   - Enter the quantity of material that arrived damaged
   - This should be in the same unit as the material

6. **Add Notes**
   - In "Discrepancy Notes", describe what happened
   - Include details like:
     - When the discrepancy was noticed
     - Condition of the material
     - Any actions taken

7. **Save or Submit**
   - The discrepancy information will be recorded
   - **Important**: Lost and damaged quantities cannot exceed the total material quantity

### When to Record Discrepancies

Record discrepancies when:
- You notice missing items during gate entry
- Material arrives in damaged condition
- Quantities don't match the reference document
- You need to document any issues for investigation

---

## Understanding Compliance Requirements

### What is Compliance?

Compliance means following legal requirements. For material leaving the facility, certain documents must be generated before the material can be dispatched.

### E-Invoice

- **What it is**: An electronic invoice required by tax authorities
- **When required**: For Sales Invoices above a certain value (threshold set by your company)
- **Where to check**: In the Compliance Details section of the Gate Pass
- **Status options**:
  - Generated: Document is ready, you can proceed
  - Not Generated: Document is missing, you cannot submit
  - Not Required: Value is below threshold, no action needed

### E-Way Bill

- **What it is**: An electronic waybill required for transporting goods
- **When required**: For dispatches above a certain value (threshold set by your company)
- **Where to check**: In the Compliance Details section
- **Status options**:
  - Generated: Document is ready, you can proceed
  - Not Generated: Document is missing, you cannot submit
  - Not Required: Value is below threshold, no action needed

### What to Do When Compliance Documents are Missing

1. **Do NOT submit the gate pass** - The system will not allow it

2. **Check the compliance status section**
   - It will clearly show which documents are missing

3. **Contact the person who created the reference document**
   - For Sales Invoices: Contact the sales team
   - For Delivery Notes: Contact the dispatch team
   - They need to generate the required documents

4. **Wait for documents to be generated**
   - Once generated, refresh the gate pass
   - The compliance status will update automatically

5. **Then submit the gate pass**

### Important Compliance Rules

- **You cannot override compliance requirements** - The system will block submission
- **Compliance is checked automatically** - You don't need to calculate thresholds
- **Always check compliance before allowing material to leave** - This is a legal requirement

---

## Viewing Reports

### Available Reports

The system provides three main reports:

1. **Pending Gate Passes** - Shows gate passes waiting for warehouse processing
2. **Gate Register** - Shows all gate pass activities (daily log)
3. **Material Reconciliation** - Shows material received vs. dispatched

### How to Access Reports

1. Go to the Gate Entry module
2. Click on "Reports" in the sidebar
3. Select the report you want to view

### Pending Gate Passes Report

**What it shows**:
- All submitted gate passes that haven't been converted to receipts yet
- How many days each gate pass has been pending
- Material details for each gate pass

**How to use it**:
- Filter by date range to see pending passes for a specific period
- Filter by supplier to see passes for a specific supplier
- Filter by company if you work with multiple companies
- Color coding:
  - Green: Less than 1 day old
  - Yellow: 1-2 days old
  - Red: More than 2 days old

**What you can do**:
- View details of pending gate passes
- See which gate passes need attention
- Track aging of pending passes

### Gate Register Report

**What it shows**:
- Complete log of all gate pass activities
- Date and time of each entry/exit
- Vehicle and driver information
- Material summary for each gate pass
- Entry type (Gate In or Gate Out)

**How to use it**:
- Filter by date range to see activities for specific dates
- Filter by entry type (Gate In or Gate Out)
- Filter by supplier/customer
- Filter by vehicle number
- Export to Excel or PDF for records

**What you can do**:
- Review daily gate activities
- Track material movements
- Generate reports for management
- Maintain audit trail

### Material Reconciliation Report

**What it shows**:
- Comparison between gate pass quantities and receipt quantities
- Discrepancies between what was recorded at gate vs. warehouse
- Item-wise breakdown of differences

**How to use it**:
- Filter by date range
- Filter by document type (Purchase Order, Sales Invoice, etc.)
- Filter by supplier/customer
- View discrepancies highlighted in red

**What you can do**:
- Identify quantity mismatches
- Investigate discrepancies
- Ensure accurate inventory records

---

## Common Scenarios

### Scenario 1: Partial Delivery from Supplier

**Situation**: A supplier arrives with only part of the ordered material.

**What to do**:
1. Create a Gate In pass for the Purchase Order
2. Click "Add Item" button
3. In the dialog, select only the items that actually arrived (check the boxes)
4. Click "Add Selected" to add those items
5. Enter the received quantities for each item
6. Submit the gate pass
7. The supplier can return later with the remaining material - you'll create another gate pass for that and add the remaining items

### Scenario 2: Multiple Vehicles for Same Order

**Situation**: One Purchase Order is delivered in multiple vehicles.

**What to do**:
1. Create the first Gate In pass with the first vehicle's details
2. Click "Add Item" and select items that are in the first vehicle
3. Enter quantities for items in the first vehicle
4. Submit the gate pass
5. Create a second Gate In pass for the same Purchase Order
6. Enter the second vehicle's details
7. Click "Add Item" and select items that are in the second vehicle
8. Enter quantities for items in the second vehicle
9. Submit the second gate pass
10. The system will track that both vehicles are for the same order

### Scenario 3: Material Arrives Without Purchase Order

**Situation**: Material arrives but there's no Purchase Order in the system.

**What to do**:
- **You cannot create a gate pass without a reference document**
- Contact the purchase department to create a Purchase Order first
- Once the Purchase Order is created, you can create the gate pass

### Scenario 4: Customer Vehicle Arrives Early

**Situation**: A customer vehicle arrives to collect material, but the Sales Invoice is not ready.

**What to do**:
- **You cannot create a gate pass without a Sales Invoice**
- The Sales Invoice must be created and submitted first
- Once ready, create the gate pass
- Check compliance documents before allowing dispatch

### Scenario 5: Material Damaged During Transit

**Situation**: Material arrives damaged from supplier.

**What to do**:
1. Create the Gate In pass normally
2. Enter the actual received quantity (including damaged items)
3. In Discrepancy Details section:
   - Check "Has Discrepancy"
   - Enter damaged quantity
   - Add notes describing the damage
4. Submit the gate pass
5. The store manager will handle the damaged material separately

### Scenario 6: Wrong Material Delivered

**Situation**: Supplier delivers different material than ordered.

**What to do**:
- **Do not create a gate pass for wrong material**
- Contact the purchase department immediately
- They will handle the situation (may need to create a new Purchase Order or return the material)
- Only create a gate pass when you have the correct reference document

### Scenario 7: Stock Entry Material Auto-Created

**Situation**: You see a draft gate pass that was automatically created.

**What to do**:
1. Open the draft gate pass
2. Verify the material details are correct
3. Complete the vehicle and driver information
4. Review all items
5. Submit the gate pass

### Scenario 9: Supplier Vehicle Arrives with Multiple Invoices on One Purchase Order

**Situation**: A supplier delivers material for one PO, but the driver has three separate delivery challans (invoice numbers).

**What to do**:
1. Create a Gate In pass and select the Purchase Order.
2. Enter vehicle and driver details.
3. Click **"Add Invoice"** and enter the first invoice number; add its items and quantities.
4. Click **"Add Invoice"** again and enter the second invoice number; add its items and quantities.
5. Repeat for the third invoice.
6. Submit the Gate Pass — your job ends here.
7. A stores user will open the submitted Gate Pass and click **"Create Purchase Receipt"** to generate one draft Purchase Receipt per invoice. No further action is required from you.

### Scenario 8: Compliance Documents Not Ready

**Situation**: You need to dispatch material but compliance documents are missing.

**What to do**:
1. Do NOT submit the gate pass
2. Check which documents are missing (E-Invoice or E-Way Bill)
3. Contact the person who created the Sales Invoice/Delivery Note
4. Ask them to generate the required documents
5. Once generated, refresh the gate pass
6. Verify compliance status shows "Generated"
7. Then submit the gate pass

---

## Troubleshooting

### Problem: Cannot find the Purchase Order in the list

**Possible causes**:
- The Purchase Order is not submitted
- The Purchase Order is closed
- You don't have permission to view it

**Solutions**:
- Ask the purchase department to submit the Purchase Order
- If the order is closed, contact your supervisor
- Contact system administrator if permission issues persist

### Problem: "Add Item" button doesn't appear

**Possible causes**:
- Reference Number is not selected
- Document Reference is not selected
- You're working on a Gate Out pass (items are auto-loaded for outbound passes)

**Solutions**:
- First select Document Reference (Purchase Order, Subcontracting Order, etc.)
- Then select Reference Number
- The "Add Item" button should appear in the Items List section
- For Gate Out passes, items are automatically loaded - you don't need to add them

### Problem: Cannot enter received quantity

**Possible causes**:
- Items haven't been added yet
- The field is read-only (for outbound passes or submitted gate passes)

**Solutions**:
- Click "Add Item" button first to select and add items
- For outbound passes (Sales Invoice, Delivery Note), quantities are automatically set and locked - you cannot change them
- If the gate pass is already submitted, you cannot edit quantities

### Problem: Cannot submit gate pass - compliance error

**Possible causes**:
- E-Invoice not generated (for Sales Invoices above threshold)
- E-Way Bill not generated (for dispatches above threshold)

**Solutions**:
- Check the Compliance Details section to see what's missing
- Contact the person who created the Sales Invoice/Delivery Note
- Ask them to generate the required documents
- Wait for documents to be generated, then try again

### Problem: Vehicle number field is empty but required

**Possible causes**:
- Sales Invoice/Delivery Note doesn't have vehicle information
- Stock Entry doesn't have vehicle information

**Solutions**:
- Enter the vehicle number manually
- Check the vehicle physically at the gate
- Enter the correct registration number

### Problem: No items appear in the Add Item dialog

**Possible causes**:
- Purchase Order/Subcontracting Order has no items
- All items have already been received (pending quantity is 0)
- All items from the reference document have already been added to this gate pass
- There's a system error

**Solutions**:
- Verify the reference document has items
- Check if all items are already received (pending quantity is 0)
- If you've already added some items, the dialog will only show items that haven't been added yet
- Contact system administrator if issue persists

### Problem: Cannot see the gate pass I just created

**Possible causes**:
- It's saved as draft and you're looking in the wrong list
- You don't have permission to view it
- It was created for a different company

**Solutions**:
- Check "Draft" gate passes in the list
- Use filters to search by date or reference number
- Contact supervisor if permission issues

### Problem: Discrepancy fields are disabled

**Possible causes**:
- "Has Discrepancy" checkbox is not checked

**Solutions**:
- Check the "Has Discrepancy" checkbox first
- Then you can enter lost and damaged quantities

### Problem: System shows error when entering quantities

**Possible causes**:
- Quantity exceeds ordered quantity
- Quantity is negative
- Invalid number format

**Solutions**:
- Enter quantity less than or equal to ordered quantity
- Enter positive numbers only
- Use decimal numbers if needed (e.g., 10.5)

---

## Important Reminders

1. **Always verify vehicle and driver information** - This is critical for security and tracking

2. **Check compliance documents for outbound material** - Never allow material to leave without required documents

3. **Enter accurate quantities** - Match what you physically see, not what the document says

4. **Record discrepancies immediately** - Don't wait, document issues as soon as you notice them

5. **Submit gate passes promptly** - Don't leave them in draft status for too long

6. **Contact the right person for issues**:
   - Purchase Orders: Purchase department
   - Sales Invoices: Sales/dispatch team
   - System errors: System administrator
   - Compliance documents: Person who created the reference document

7. **Keep the gate pass number** - You may need to reference it later

8. **Double-check before submitting** - Once submitted, changes require cancellation and recreation

---

## Getting Help

If you encounter any issues or have questions:

1. **Check this guide first** - Most common scenarios are covered

2. **Contact your supervisor** - For process-related questions

3. **Contact the relevant department**:
   - Purchase issues: Purchase department
   - Sales/dispatch issues: Sales team
   - Warehouse issues: Store manager

4. **System administrator** - For technical problems or access issues

---

## Quick Reference

### Required Fields for All Gate Passes
- Document Reference
- Reference Number
- Company
- Vehicle Number
- Driver Name
- Security Guard Name
- Gate Pass Date and Time
- At least one item with quantity

### Gate In Passes
- Purchase Order
- Subcontracting Order
- Stock Entry (for returns)

### Gate Out Passes
- Sales Invoice
- Delivery Note
- Stock Entry (for dispatches)

### Compliance Check (Gate Out Only)
- E-Invoice status (Sales Invoice)
- E-Way Bill status (if value above threshold)

### Status Flow
Draft → Submitted → Receipt Created

---

*Last Updated: Based on Gate Entry Module v1.0.0*

