
from google import genai
import csv
import json
import os
import re
import sys
import concurrent.futures
import threading
from typing import List, Dict, Tuple

API_KEY = "AIzaSyCGNWZxWrG8xuN_JwObnLeGknD7zpX5RUU"
# The instruction prompt template
PROMPT_TEMPLATE = """
You're given bank transaction data in a table format. Write a JSON object with two keys:

• rules: An object where each key is a keyword or phrase you spot in the Description field, and its value is a human-friendly category name. 
  IMPORTANT: Extract the most distinctive and common parts of merchant/service names, not the full description. 
  For example:
  - "ALLY BANK $TRANSFER" → use "ALLY BANK" as keyword
  - "CAPITAL ONE CRCARDPMT" → use "CAPITAL ONE" as keyword  
  - "DISCOVER E-PAYMENT" → use "DISCOVER" as keyword
  - "VENMO PAYMENT" → use "VENMO" as keyword
  - "FID BKG SVC LLC MONEYLINE" → use "FID BKG SVC" as keyword
  Focus on the core merchant/service name that would appear across multiple similar transactions.

  CATEGORIZATION GUIDELINES:
  - All bank transfers, P2P transfers, account transfers, wire transfers should be categorized as "Transfers"
  - Credit card payments should be categorized as "Credit Card Payments" 
  - Investment/brokerage transactions should be categorized as "Investments"
  - Salary/payroll should be categorized as "Income - Salary"
  - Subscriptions should be categorized as "Subscriptions"
  - Be consistent with category names across all transactions

• notes: An array of summary strings, one per category, that include:
  – The category name  
  – The number of transactions in that category  
  – The total amount for that category. For expenses (Debit column), show as negative dollars (e.g. -$1590.00). For income (Credit column), show as positive dollars (e.g. +$1200.00).

Important: Analyze BOTH debits (expenses/outgoing) AND credits (income/incoming) transactions. Categories should reflect whether they are income or expenses.

Only output the final JSON.

Here's the table (columns separated by pipes):
{table}
"""

# Thread lock for safe printing
print_lock = threading.Lock()

def thread_safe_print(message, file=sys.stdout):
    with print_lock:
        print(message, file=file)

def prompt_gemini(chunk_data: Tuple[int, str]) -> Tuple[int, dict]:
    chunk_num, table_text = chunk_data
    client = genai.Client(api_key=API_KEY)
    full_prompt = PROMPT_TEMPLATE.format(table=table_text)
    
    thread_safe_print(f"[Chunk {chunk_num}] Sending request to Gemini API...")
    
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt
        )
        
        thread_safe_print(f"[Chunk {chunk_num}] Raw response from Gemini: {resp.text[:200]}...")
        
        try:
            result = json.loads(resp.text)
            thread_safe_print(f"[Chunk {chunk_num}] Successfully parsed JSON response")
            return chunk_num, result
        except json.JSONDecodeError as e:
            thread_safe_print(f"[Chunk {chunk_num}] JSON decode error: {e}", file=sys.stderr)
            thread_safe_print(f"[Chunk {chunk_num}] Full response text: {resp.text}", file=sys.stderr)
            
            # Try to extract JSON from the response if it's wrapped in markdown
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', resp.text, re.DOTALL)
            if json_match:
                thread_safe_print(f"[Chunk {chunk_num}] Found JSON in markdown blocks, attempting to parse...")
                try:
                    result = json.loads(json_match.group(1))
                    thread_safe_print(f"[Chunk {chunk_num}] Successfully parsed JSON from markdown")
                    return chunk_num, result
                except json.JSONDecodeError:
                    pass
            
            # Return empty structure if parsing fails
            thread_safe_print(f"[Chunk {chunk_num}] Returning empty structure due to parsing failure", file=sys.stderr)
            return chunk_num, {"rules": {}, "notes": []}
            
    except Exception as e:
        thread_safe_print(f"[Chunk {chunk_num}] API call failed: {e}", file=sys.stderr)
        return chunk_num, {"rules": {}, "notes": []}

def chunked_reader(reader, chunk_size):
    chunk = []
    for row in reader:
        chunk.append(row)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk

def build_table_str(headers, rows):
    # join headers and rows with " | "
    lines = [" | ".join(headers)]
    for row in rows:
        lines.append(" | ".join(row))
    return "\n".join(lines)

def merge_rules(master, new, chunk_num):
    thread_safe_print(f"[Chunk {chunk_num}] Merging {len(new)} new rules into master rules...")
    for key, cat in new.items():
        if key in master and master[key] != cat:
            thread_safe_print(f"[Chunk {chunk_num}] Warning: keyword '{key}' mapped to both '{master[key]}' and '{cat}'", file=sys.stderr)
        master[key] = cat
        thread_safe_print(f"[Chunk {chunk_num}]   Added rule: '{key}' -> '{cat}'")

def parse_and_agg_notes(master_stats, notes_list, chunk_num):
    # Handle various note formats that Gemini might return
    thread_safe_print(f"[Chunk {chunk_num}] Processing {len(notes_list)} notes...")
    
    # Try multiple patterns to handle different formats
    patterns = [
        # "Bank/P2P Transfers: 5 transactions totaling -$1303.00."
        re.compile(r"^(.*?):\s*(\d+)\s+transactions?\s+totaling\s+([+-]?\$\d+\.\d{2})\.?$"),
        # "P2P Income – 1 transaction – +$800.00"
        re.compile(r"^(.*?)\s*[–-]\s*(\d+)\s+transactions?\s*[–-]\s*([+-]?\$\d+\.\d{2})\.?$"),
        # "Transfers Out: 2 transactions, total -$1590.00."
        re.compile(r"^(.*?):\s*(\d+)\s+transactions?,\s*total\s+([+-]?\$\d+\.\d{2})\.?$"),
        # "Online Subscriptions: 1 transactions, total -$10.74."
        re.compile(r"^(.*?):\s*(\d+)\s+transactions?,\s*total\s+([+-]?\$\d+\.\d{2})\.?$"),
        # More flexible: any format with category, number, and amount
        re.compile(r"^(.*?)[:\-–]\s*(\d+)\s+.*?([+-]?\$\d+\.\d{2})\.?$")
    ]
    
    for note in notes_list:
        thread_safe_print(f"[Chunk {chunk_num}]   Processing note: {note}")
        
        parsed = False
        for i, pattern in enumerate(patterns):
            m = pattern.match(note)
            if m:
                thread_safe_print(f"[Chunk {chunk_num}]     Matched pattern {i+1}")
                cat, cnt, amt_str = m.groups()
                cnt = int(cnt)
                # Parse amount, handling both positive and negative values
                amt_str = amt_str.replace('$', '').replace('+', '')
                amt = float(amt_str)
                
                if cat not in master_stats:
                    master_stats[cat] = {"count": 0, "total": 0.0}
                    thread_safe_print(f"[Chunk {chunk_num}]     Created new category: {cat}")
                master_stats[cat]["count"] += cnt
                master_stats[cat]["total"] += amt
                thread_safe_print(f"[Chunk {chunk_num}]     Updated {cat}: {master_stats[cat]['count']} transactions, ${master_stats[cat]['total']:.2f}")
                parsed = True
                break
        
        if not parsed:
            thread_safe_print(f"[Chunk {chunk_num}] Could not parse note: {note}", file=sys.stderr)
            # Try to extract at least the category name and amount manually
            try:
                # Look for category name before colon or dash
                cat_match = re.search(r"^([^:\-–]+)", note)
                # Look for amount in the note
                amt_match = re.search(r"([+-]?\$\d+\.\d{2})", note)
                # Look for transaction count
                cnt_match = re.search(r"(\d+)\s+transactions?", note)
                
                if cat_match and amt_match and cnt_match:
                    cat = cat_match.group(1).strip()
                    amt_str = amt_match.group(1).replace('$', '').replace('+', '')
                    amt = float(amt_str)
                    cnt = int(cnt_match.group(1))
                    
                    if cat not in master_stats:
                        master_stats[cat] = {"count": 0, "total": 0.0}
                        thread_safe_print(f"[Chunk {chunk_num}]     Created new category (manual): {cat}")
                    master_stats[cat]["count"] += cnt
                    master_stats[cat]["total"] += amt
                    thread_safe_print(f"[Chunk {chunk_num}]     Updated (manual): {cat}: {master_stats[cat]['count']} transactions, ${master_stats[cat]['total']:.2f}")
                else:
                    thread_safe_print(f"[Chunk {chunk_num}]     Manual parsing also failed", file=sys.stderr)
            except Exception as e:
                thread_safe_print(f"[Chunk {chunk_num}]     Manual parsing error: {e}", file=sys.stderr)

def find_best_category_match(description, rules):
    """Find the best matching category for a transaction description using flexible matching."""
    description_upper = description.upper()
    
    # Try exact keyword matches first (case-insensitive)
    for rule_keyword, rule_category in rules.items():
        if rule_keyword.upper() in description_upper:
            return rule_category
    
    # Try partial matches - split keywords and look for individual words
    for rule_keyword, rule_category in rules.items():
        rule_words = rule_keyword.upper().split()
        # If all words in the rule keyword are found in the description
        if all(word in description_upper for word in rule_words):
            return rule_category
    
    # Try fuzzy matching - look for similar patterns
    for rule_keyword, rule_category in rules.items():
        rule_upper = rule_keyword.upper()
        # Check if description contains most of the rule keyword (at least 70% of characters)
        if len(rule_upper) > 3:  # Only for longer keywords
            matches = sum(1 for char in rule_upper if char in description_upper)
            if matches / len(rule_upper) >= 0.7:
                return rule_category
    
    return None

def categorize_all_transactions(filepath, rules):
    """Process the entire CSV using the generated rules to categorize and total all transactions."""
    print(f"\n--- Categorizing All Transactions Using Generated Rules ---")
    
    category_totals = {}
    uncategorized_transactions = []
    total_transactions = 0
    
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        print(f"CSV headers: {headers}")
        
        # Find column indices - handle both old and new formats
        desc_idx = headers.index('Description')
        
        # Check if we have the new format (Amount column) or old format (Debit/Credit columns)
        if 'Amount' in headers:
            amount_idx = headers.index('Amount')
            new_format = True
        else:
            debit_idx = headers.index('Debit')
            credit_idx = headers.index('Credit')
            new_format = False
        
        for row in reader:
            total_transactions += 1
            description = row[desc_idx]
            
            # Parse amount based on format
            if new_format:
                amount_str = row[amount_idx].strip()
                if not amount_str:
                    continue  # Skip if no amount
                
                # Remove dollar sign and handle parentheses for negative amounts
                amount_str = amount_str.replace('$', '')
                if amount_str.startswith('(') and amount_str.endswith(')'):
                    # Negative amount in parentheses
                    amount = -float(amount_str[1:-1])
                    transaction_type = "expense"
                else:
                    # Positive amount
                    amount = float(amount_str)
                    transaction_type = "income"
            else:
                # Old format with separate Debit/Credit columns
                debit = row[debit_idx].strip()
                credit = row[credit_idx].strip()
                
                if debit:
                    amount = -float(debit)  # Negative for expenses
                    transaction_type = "expense"
                elif credit:
                    amount = float(credit)  # Positive for income
                    transaction_type = "income"
                else:
                    continue  # Skip if no amount
            
            # Find matching rule using improved matching
            category = find_best_category_match(description, rules)
            
            if category:
                if category not in category_totals:
                    category_totals[category] = {
                        "count": 0,
                        "total": 0.0,
                        "income": 0.0,
                        "expenses": 0.0
                    }
                
                category_totals[category]["count"] += 1
                category_totals[category]["total"] += amount
                
                if transaction_type == "income":
                    category_totals[category]["income"] += amount
                else:
                    category_totals[category]["expenses"] += abs(amount)
            else:
                uncategorized_transactions.append({
                    "description": description,
                    "amount": amount,
                    "type": transaction_type
                })
    
    # Print categorized summary
    print(f"\nProcessed {total_transactions} transactions")
    print(f"Categorized: {total_transactions - len(uncategorized_transactions)}")
    print(f"Uncategorized: {len(uncategorized_transactions)}")
    
    print(f"\n--- Category Totals ---")
    
    # Sort categories by total amount (largest expenses first, then income)
    sorted_categories = sorted(category_totals.items(), 
                              key=lambda x: x[1]["total"])
    
    for category, data in sorted_categories:
        count = data["count"]
        total = data["total"]
        income = data["income"]
        expenses = data["expenses"]
        
        if total < 0:
            print(f"{category}: {count} transactions, -${abs(total):.2f} (${expenses:.2f} expenses)")
        else:
            print(f"{category}: {count} transactions, +${total:.2f} (${income:.2f} income)")
    
    # Separate categories based on AI-generated category names
    income_categories = {}
    expense_categories = {}
    transfer_categories = {}
    
    for category, data in category_totals.items():
        category_lower = category.lower()
        
        # Check if this is a transfer category based on AI-generated category name
        if "transfer" in category_lower:
            transfer_categories[category] = data
        # Check for mixed categories (both income and expenses) - likely transfers or credit cards
        elif data["income"] > 0 and data["expenses"] > 0:
            # If it's clearly a credit card payment category, separate the income/expense parts
            if "credit card" in category_lower or "payment" in category_lower:
                # Split into income and expense parts
                if data["income"] > 0:
                    income_cat_name = f"{category} (Refunds/Returns)"
                    income_categories[income_cat_name] = {
                        "count": data["count"],
                        "total": data["income"],
                        "income": data["income"],
                        "expenses": 0.0
                    }
                if data["expenses"] > 0:
                    expense_cat_name = f"{category} (Payments)"
                    expense_categories[expense_cat_name] = {
                        "count": data["count"],
                        "total": -data["expenses"],
                        "income": 0.0,
                        "expenses": data["expenses"]
                    }
            else:
                # Treat as transfer if it has both income and expenses
                transfer_categories[category] = data
        # Pure income categories
        elif data["income"] > 0 and data["expenses"] == 0:
            income_categories[category] = data
        # Pure expense categories
        elif data["expenses"] > 0 and data["income"] == 0:
            expense_categories[category] = data
    
    # Calculate totals excluding transfers
    total_income_no_transfers = sum(data["income"] for data in income_categories.values())
    total_expenses_no_transfers = sum(data["expenses"] for data in expense_categories.values())
    total_transfers = sum(abs(data["total"]) for data in transfer_categories.values())
    
    print(f"\n--- Income vs Expenses Summary (Excluding Transfers) ---")
    
    # Sort income and expense categories
    sorted_income = sorted(income_categories.items(), key=lambda x: x[1]["income"], reverse=True)
    sorted_expenses = sorted(expense_categories.items(), key=lambda x: x[1]["expenses"], reverse=True)
    
    # Print side by side
    max_rows = max(len(sorted_income), len(sorted_expenses))
    
    print(f"{'INCOME CATEGORIES':<50} {'EXPENSE CATEGORIES':<50}")
    print(f"{'-' * 50} {'-' * 50}")
    
    for i in range(max_rows):
        income_line = ""
        expense_line = ""
        
        if i < len(sorted_income):
            cat, data = sorted_income[i]
            income_line = f"{cat}: +${data['income']:.2f} ({data['count']} txns)"
        
        if i < len(sorted_expenses):
            cat, data = sorted_expenses[i]
            expense_line = f"{cat}: -${data['expenses']:.2f} ({data['count']} txns)"
        
        print(f"{income_line:<50} {expense_line:<50}")
    
    print(f"{'-' * 50} {'-' * 50}")
    print(f"{'TOTAL INCOME: +$' + f'{total_income_no_transfers:.2f}':<50} {'TOTAL EXPENSES: -$' + f'{total_expenses_no_transfers:.2f}':<50}")
    
    # Show transfer summary separately
    if transfer_categories:
        print(f"\n--- Transfer Summary (Not Income/Expense) ---")
        for category, data in sorted(transfer_categories.items(), key=lambda x: abs(x[1]["total"]), reverse=True):
            print(f"{category}: ${abs(data['total']):.2f} ({data['count']} transactions)")
        print(f"Total Transfer Volume: ${total_transfers:.2f}")
    
    print(f"\n--- Overall Financial Summary ---")
    print(f"Total Income: +${total_income_no_transfers:.2f}")
    print(f"Total Expenses: -${total_expenses_no_transfers:.2f}")
    print(f"Net Income: ${total_income_no_transfers - total_expenses_no_transfers:.2f}")
    print(f"Transfer Volume: ${total_transfers:.2f} (excluded from income/expense)")
    
    # Show uncategorized transactions
    if uncategorized_transactions:
        print(f"\n--- Uncategorized Transactions ({len(uncategorized_transactions)}) ---")
        uncategorized_income = 0
        uncategorized_expenses = 0
        
        for trans in uncategorized_transactions[:10]:  # Show first 10
            if trans["type"] == "income":
                uncategorized_income += trans["amount"]
                print(f"  +${trans['amount']:.2f}: {trans['description']}")
            else:
                uncategorized_expenses += abs(trans["amount"])
                print(f"  -${abs(trans['amount']):.2f}: {trans['description']}")
        
        if len(uncategorized_transactions) > 10:
            print(f"  ... and {len(uncategorized_transactions) - 10} more")
        
        print(f"\nUncategorized Income: +${uncategorized_income:.2f}")
        print(f"Uncategorized Expenses: -${uncategorized_expenses:.2f}")
        print(f"Uncategorized Net: ${uncategorized_income - uncategorized_expenses:.2f}")
    
    return {
        "category_totals": category_totals,
        "income_categories": income_categories,
        "expense_categories": expense_categories,
        "transfer_categories": transfer_categories,
        "uncategorized": uncategorized_transactions,
        "summary": {
            "total_income": total_income_no_transfers,
            "total_expenses": total_expenses_no_transfers,
            "net_amount": total_income_no_transfers - total_expenses_no_transfers,
            "transfer_volume": total_transfers,
            "total_transactions": total_transactions,
            "categorized_count": total_transactions - len(uncategorized_transactions),
            "uncategorized_count": len(uncategorized_transactions)
        }
    }

def main():
    filepath = "history2.csv"
    if not os.path.isfile(filepath):
        print(f"File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading CSV file: {filepath}")
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        print(f"CSV headers: {headers}")

        # Collect all chunks first
        chunks = []
        chunk_count = 0
        for chunk in chunked_reader(reader, 50):
            chunk_count += 1
            table_text = build_table_str(headers, chunk)
            chunks.append((chunk_count, table_text))
            print(f"Prepared chunk {chunk_count} ({len(chunk)} rows)")

        print(f"\nTotal chunks to process: {len(chunks)}")
        print("Starting parallel processing...")

        master_rules = {}
        master_stats = {}
        
        # Process chunks in parallel
        max_workers = min(5, len(chunks))  # Limit concurrent API calls
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            print(f"Using {max_workers} parallel workers")
            
            # Submit all tasks
            future_to_chunk = {executor.submit(prompt_gemini, chunk_data): chunk_data[0] 
                             for chunk_data in chunks}
            
            # Process results as they complete
            completed = 0
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_num = future_to_chunk[future]
                try:
                    result_chunk_num, result = future.result()
                    completed += 1
                    
                    print(f"\n--- Processing results for chunk {result_chunk_num} ({completed}/{len(chunks)} complete) ---")
                    
                    # Merge rules (thread-safe since we're processing results sequentially)
                    merge_rules(master_rules, result.get("rules", {}), result_chunk_num)
                    
                    # Aggregate notes
                    parse_and_agg_notes(master_stats, result.get("notes", []), result_chunk_num)
                    
                    print(f"Current totals: {len(master_rules)} rules, {len(master_stats)} categories")
                    
                except Exception as exc:
                    print(f'Chunk {chunk_num} generated an exception: {exc}', file=sys.stderr)

    print(f"\n--- Final Processing Complete ---")
    print(f"Total rules collected: {len(master_rules)}")
    print(f"Total categories: {len(master_stats)}")

    # Build the final notes array with proper formatting for positive/negative amounts
    final_notes = []
    for cat, data in master_stats.items():
        total = data['total']
        if total >= 0:
            final_notes.append(f"{cat}: {data['count']} transactions totaling +${total:.2f}")
        else:
            final_notes.append(f"{cat}: {data['count']} transactions totaling -${abs(total):.2f}")

    final_output = {
        "rules": master_rules,
        "notes": final_notes
    }

    print("\n--- Final Output ---")
    print(json.dumps(final_output, indent=2))
    
    # Categorize all transactions using the generated rules
    categorization_results = categorize_all_transactions(filepath, master_rules)
    
    # Optionally save the complete analysis to a file
    complete_analysis = {
        "rules": master_rules,
        "notes": final_notes,
        "full_categorization": categorization_results
    }
    
    with open("financial_analysis.json", "w") as f:
        json.dump(complete_analysis, f, indent=2)
    
    print(f"\nComplete analysis saved to: financial_analysis.json")

if __name__ == "__main__":
    main()
