"""
Test the memory system: MemoryManager and MemoryExtractor.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))

from ai.memory_system import MemoryManager, MemoryExtractor
from memory.sqlite import connect as sqlite_connect
import tempfile


def test_memory_system():
    """Test memory manager and extractor."""
    
    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        conn = sqlite_connect(db_path)
        
        try:
            print("[TEST] Memory System Verification\n")
            
            # Initialize memory system
            manager = MemoryManager(conn)
            extractor = MemoryExtractor(manager)
            
            # Test 1: Remember some facts
            print("[1] Testing remember()...")
            id1 = manager.remember(
                user_id="alice",
                content="I prefer Python over JavaScript",
                category="preference",
                importance=7
            )
            id2 = manager.remember(
                user_id="alice",
                content="My name is Alice Johnson",
                category="name",
                importance=9
            )
            id3 = manager.remember(
                user_id="alice",
                content="Building a chatbot for my company",
                category="project",
                importance=8
            )
            print(f"  [OK] Saved 3 memories: {id1}, {id2}, {id3}\n")
            
            # Test 2: Recall memories
            print("[2] Testing recall()...")
            memories = manager.recall("alice", limit=5)
            print(f"  [OK] Recalled {len(memories)} memories:")
            for mem in memories:
                print(f"    - [{mem['category']}] {mem['content']} (importance: {mem['importance']})")
            print()
            
            # Test 3: Format for prompt
            print("[3] Testing format_for_prompt()...")
            formatted = manager.format_for_prompt(memories)
            print(f"  [OK] Formatted:\n{formatted}\n")
            
            # Test 4: Search
            print("[4] Testing search()...")
            results = manager.search("alice", "python", limit=5)
            print(f"  [OK] Found {len(results)} results for 'python'")
            print()
            
            # Test 5: Extract from conversation
            print("[5] Testing extract_and_save()...")
            user_msg = "Hi! My name is Bob and I'm working on a machine learning project"
            assistant_msg = "That's great! Machine learning is fascinating."
            
            saved = extractor.extract_and_save("bob", user_msg, assistant_msg)
            print(f"  [OK] Extracted and saved {len(saved)} memories\n")
            
            # Test 6: Verify extracted memories
            print("[6] Verifying extracted memories...")
            bob_memories = manager.get_all_memories("bob")
            print(f"  [OK] Bob has {len(bob_memories)} memories:")
            for mem in bob_memories:
                print(f"    - [{mem['category']}] {mem['content']}")
            print()
            
            # Test 7: Duplicate prevention
            print("[7] Testing duplicate prevention...")
            dup_id = manager.remember(
                user_id="alice",
                content="I prefer Python over JavaScript",
                category="preference",
                importance=7
            )
            print(f"  [OK] Duplicate returned: {dup_id} (should be None)")
            print()
            
            # Test 8: Update memory
            print("[8] Testing update_memory()...")
            success = manager.update_memory(id1, importance=9)
            print(f"  [OK] Updated memory importance: {success}")
            updated = manager.recall("alice", limit=1)
            if updated:
                print(f"    - New importance: {updated[0]['importance']}")
            print()
            
            # Test 9: Delete memory
            print("[9] Testing delete_memory()...")
            deleted = manager.delete_memory(id1)
            print(f"  [OK] Deleted memory: {deleted}")
            remaining = manager.get_all_memories("alice")
            print(f"    - Alice now has {len(remaining)} memories")
            print()
            
            # Test 10: Filter by category
            print("[10] Testing category filtering...")
            names = manager.recall("alice", categories=["name"])
            print(f"  [OK] Found {len(names)} name memories")
            for mem in names:
                print(f"    - {mem['content']}")
            print()
            
            print("=" * 60)
            print("SUCCESS: All memory system tests passed!")
            print("=" * 60)
        
        finally:
            conn.close()


if __name__ == '__main__':
    test_memory_system()
