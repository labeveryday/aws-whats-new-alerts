#!/usr/bin/env python3
"""
Validate AgentCore Memory for AWS Newsletter Agent

Uses boto3 to inspect memory contents and validate that articles are being stored correctly.
"""
import boto3
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Configuration
MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
REGION = os.getenv("AWS_REGION", "us-west-2")
ACTOR_ID = os.getenv("AGENT_ACTOR_ID", "aws-newsletter-bot")
SESSION_ID = os.getenv("AGENT_SESSION_ID", "aws-newsletter-main-session")

class AgentCoreMemoryValidator:
    """Validate and inspect AgentCore Memory using boto3"""
    
    def __init__(self, memory_id: str, region: str = "us-west-2"):
        self.memory_id = memory_id
        self.region = region
        self.control_client = boto3.client('bedrock-agentcore-control', region_name=region)
        self.runtime_client = boto3.client('bedrock-agentcore', region_name=region)
    
    def get_memory_info(self) -> Dict:
        """Get basic memory information"""
        try:
            response = self.control_client.get_memory(memoryId=self.memory_id)
            return response
        except Exception as e:
            return {"error": f"Failed to get memory info: {str(e)}"}
    
    def list_memories(self) -> Dict:
        """List all memories in the account"""
        try:
            response = self.control_client.list_memories()
            return response
        except Exception as e:
            return {"error": f"Failed to list memories: {str(e)}"}
    
    def query_memory(self, query: str, namespace: str = "/newsletter/facts", max_results: int = 20) -> Dict:
        """Query memory for specific content using semantic search"""
        try:
            response = self.runtime_client.retrieve_memory_records(
                memoryId=self.memory_id,
                namespace=namespace,
                searchCriteria={
                    'searchQuery': query
                },
                maxResults=max_results
            )
            return response
        except Exception as e:
            return {"error": f"Failed to query memory: {str(e)}"}
    
    def get_memory_records(self, namespace: str = "/newsletter/facts", max_results: int = 50) -> Dict:
        """Get memory records for a specific namespace"""
        try:
            response = self.runtime_client.list_memory_records(
                memoryId=self.memory_id,
                namespace=namespace,
                maxResults=max_results
            )
            return response
        except Exception as e:
            return {"error": f"Failed to get memory records: {str(e)}"}
    
    def get_all_memory_records(self, max_results: int = 100) -> Dict:
        """Get all memory records across all namespaces"""
        try:
            # Try without namespace to see all records
            response = self.runtime_client.list_memory_records(
                memoryId=self.memory_id,
                maxResults=max_results
            )
            return response
        except Exception as e:
            return {"error": f"Failed to get all memory records: {str(e)}"}

def print_memory_summary(validator: AgentCoreMemoryValidator):
    """Print a summary of memory status"""
    print("🧠 AgentCore Memory Validation Report")
    print("=" * 60)
    print(f"Memory ID: {MEMORY_ID}")
    print(f"Region: {REGION}")
    print(f"Actor ID: {ACTOR_ID}")
    print(f"Session ID: {SESSION_ID}")
    print()
    
    # Get memory info
    print("📋 Memory Information:")
    memory_info = validator.get_memory_info()
    if "error" in memory_info:
        print(f"❌ Error: {memory_info['error']}")
        return
    
    print(f"   Name: {memory_info.get('memoryName', 'N/A')}")
    print(f"   Description: {memory_info.get('description', 'N/A')}")
    print(f"   Status: {memory_info.get('status', 'N/A')}")
    print(f"   Created: {memory_info.get('createdAt', 'N/A')}")
    print(f"   Updated: {memory_info.get('updatedAt', 'N/A')}")
    print()
    
    # Get actual namespaces from memory configuration
    memory_info = validator.get_memory_info()
    actual_namespaces = []
    if "error" not in memory_info and "memory" in memory_info:
        strategies = memory_info["memory"].get("strategies", [])
        for strategy in strategies:
            actual_namespaces.extend(strategy.get("namespaces", []))
    
    # Use actual namespaces if found, otherwise fall back to expected ones
    namespaces = actual_namespaces if actual_namespaces else ["/newsletter/facts", "/newsletter/articles"]
    
    print(f"🔧 Checking namespaces: {namespaces}")
    total_records = 0
    
    for namespace in namespaces:
        print(f"📚 Memory Records in {namespace}:")
        records = validator.get_memory_records(namespace)
        if "error" in records:
            print(f"❌ Error: {records['error']}")
        else:
            record_list = records.get('memoryRecords', [])
            total_records += len(record_list)
            print(f"   Total records: {len(record_list)}")
            
            if record_list:
                print("   Recent records:")
                for i, record in enumerate(record_list[:5]):  # Show first 5
                    record_id = record.get('memoryRecordId', 'Unknown')
                    timestamp = record.get('createdAt', 'Unknown')
                    actor_id = record.get('actorId', 'Unknown')
                    session_id = record.get('sessionId', 'Unknown')
                    content_preview = record.get('content', {}).get('text', '')[:80]
                    print(f"   {i+1}. Actor:{actor_id} Session:{session_id}")
                    print(f"      Created: {timestamp}")
                    print(f"      Content: {content_preview}...")
                    print()
            else:
                print("   No records found")
        print()
    
    print(f"📊 Total records across all configured namespaces: {total_records}")
    print()

def query_processed_articles(validator: AgentCoreMemoryValidator):
    """Query for processed AWS articles"""
    print("🔍 Querying for Processed Articles:")
    print("-" * 40)
    
    queries = [
        "What AWS articles have been processed?",
        "List article URLs that were included in newsletters", 
        "Show AWS announcements from recent newsletters",
        "What AWS AI/ML articles were processed?"
    ]
    
    # Get actual namespaces from memory configuration  
    memory_info = validator.get_memory_info()
    actual_namespaces = []
    if "error" not in memory_info and "memory" in memory_info:
        strategies = memory_info["memory"].get("strategies", [])
        for strategy in strategies:
            actual_namespaces.extend(strategy.get("namespaces", []))
    
    namespaces_to_search = actual_namespaces if actual_namespaces else ["/newsletter/facts", "/newsletter/articles"]
    
    for query in queries:
        print(f"\nQuery: {query}")
        
        total_found = 0
        for namespace in namespaces_to_search:
            result = validator.query_memory(query, namespace, max_results=10)
            
            if "error" in result:
                print(f"❌ Error in {namespace}: {result['error']}")
                continue
            
            memories = result.get('memoryRecords', [])
            total_found += len(memories)
            
            if memories:
                print(f"📊 Found {len(memories)} results in {namespace}")
                for i, memory in enumerate(memories[:3]):  # Show first 3
                    content = memory.get('content', {}).get('text', 'No content')
                    score = memory.get('relevanceScore', 0)
                    actor_id = memory.get('actorId', 'Unknown')
                    session_id = memory.get('sessionId', 'Unknown')
                    print(f"   {i+1}. (Score: {score:.2f}) Actor:{actor_id} Session:{session_id}")
                    print(f"      {content[:100]}...")
        
        if total_found == 0:
            print("   No relevant memories found in any namespace")

def validate_deduplication(validator: AgentCoreMemoryValidator):
    """Validate that deduplication is working"""
    print("\n🔄 Deduplication Validation:")
    print("-" * 40)
    
    # Query for specific article patterns
    dedup_queries = [
        "aws.amazon.com/about-aws/whats-new",
        "article URLs from newsletters", 
        "processed announcement links"
    ]
    
    all_urls = set()
    
    for query in dedup_queries:
        # Get actual namespaces from memory configuration
        memory_info = validator.get_memory_info()
        actual_namespaces = []
        if "error" not in memory_info and "memory" in memory_info:
            strategies = memory_info["memory"].get("strategies", [])
            for strategy in strategies:
                actual_namespaces.extend(strategy.get("namespaces", []))
        
        namespaces_to_check = actual_namespaces if actual_namespaces else ["/newsletter/facts", "/newsletter/articles"]
        
        for namespace in namespaces_to_check:
            result = validator.query_memory(query, namespace, max_results=20)
            
            if "error" not in result:
                memories = result.get('memoryRecords', [])
                for memory in memories:
                    content = memory.get('content', {}).get('text', '')
                    # Extract URLs from content (simple pattern matching)
                    if 'aws.amazon.com' in content:
                        # This is a simplified URL extraction - could be improved
                        words = content.split()
                        for word in words:
                            if 'aws.amazon.com' in word:
                                all_urls.add(word.strip('.,()[]'))
    
    print(f"📊 Found {len(all_urls)} unique AWS URLs in memory")
    if all_urls:
        print("   Sample URLs:")
        for i, url in enumerate(list(all_urls)[:5]):
            print(f"   {i+1}. {url}")
    
    print(f"\n✅ Deduplication status: {'Working' if len(all_urls) > 0 else 'No URLs found in memory'}")

def main():
    """Main validation function"""
    if not MEMORY_ID:
        print("❌ Error: BEDROCK_AGENTCORE_MEMORY_ID not set in environment")
        print("   Run: python generate_env.py --agent-dir to generate .env file")
        return 1
    
    try:
        validator = AgentCoreMemoryValidator(MEMORY_ID, REGION)
        
        # Run validation checks
        print_memory_summary(validator)
        query_processed_articles(validator)
        validate_deduplication(validator)
        
        print("\n" + "=" * 60)
        print("✅ Memory validation complete!")
        print("\n💡 Tips:")
        print("   - Run your agent a few times to populate memory")
        print("   - Check that article URLs are being stored")
        print("   - Memory should prevent duplicate articles")
        
        return 0
        
    except Exception as e:
        print(f"❌ Validation failed: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())