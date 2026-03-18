import math

def calculate_viewport_state(total_items, items_per_screen, buffer_abs_offset, viewport_offset):
    global_total_pages = math.ceil(total_items / items_per_screen) if items_per_screen else 1
    current_item_index = buffer_abs_offset + viewport_offset
    current_page = (current_item_index // items_per_screen) + 1
    current_page = min(current_page, global_total_pages)
    return current_page, global_total_pages

def simulate_jump_last(total_items, items_per_screen, server_pg_size):
    # Goal: Calculate the exact buffer_abs_offset and viewport_offset after a jump to last
    # server_pg_size is usually 100 for Codex
    
    # 1. Which server page contains the last items?
    last_page_idx = (total_items - 1) // server_pg_size
    # If 1-indexed, this is page 32 for 3188 items
    
    # 2. What is the abs_offset for that page?
    # Codex uses 1-based indexing for p/X/Y usually, but we detected base 1.
    # So page 32 starts at (32-1)*100 = 3100.
    buffer_abs_offset = last_page_idx * server_pg_size
    
    # 3. How many items are in that last buffer?
    items_in_last_buffer = total_items - buffer_abs_offset # e.g. 3188 - 3100 = 88
    
    # 4. Where should the last screen start globally?
    target_global_start = ((total_items - 1) // items_per_screen) * items_per_screen
    
    # 5. What is the viewport_offset within that buffer?
    viewport_offset = target_global_start - buffer_abs_offset
    
    # Verify
    curr, total = calculate_viewport_state(total_items, items_per_screen, buffer_abs_offset, viewport_offset)
    return {
        "target_global_start": target_global_start,
        "buffer_abs_offset": buffer_abs_offset,
        "viewport_offset": viewport_offset,
        "virt_pg": curr,
        "total_virt_pg": total
    }

def run_tests():
    print("--- Test 1: 15 items/scr (Log Case) ---")
    res = simulate_jump_last(3188, 15, 100)
    print(f"Result: {res}")
    # Target: 3180. virt_pg should be 213 of 213.
    assert res["virt_pg"] == 213
    assert res["total_virt_pg"] == 213

    print("\n--- Test 2: 20 items/scr (Resize Case) ---")
    res = simulate_jump_last(3188, 20, 100)
    print(f"Result: {res}")
    # Target: 3180. virt_pg should be 160 of 160.
    assert res["virt_pg"] == 160
    assert res["total_virt_pg"] == 160

    print("\n--- Test 3: Edge Case (Total items < page size) ---")
    res = simulate_jump_last(45, 20, 100)
    print(f"Result: {res}")
    # Page 1 starts at 0. Target: 40. virt_pg should be 3 of 3.
    assert res["virt_pg"] == 3

    print("\nAll math checks out!")

if __name__ == "__main__":
    run_tests()
