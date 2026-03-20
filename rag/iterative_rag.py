"""
Adaptive Iterative RAG (AIR-RAG) implementation
Retrieves, analyzes, refines, and re-retrieves for better code understanding
"""

import logging
import re
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class IterativeRAG:
    """
    Implements iterative retrieval with feedback loops
    """
    
    def __init__(self, retriever, llm, max_iterations=3, similarity_threshold=0.7):
        self.retriever = retriever
        self.llm = llm
        self.max_iterations = max_iterations
        self.similarity_threshold = similarity_threshold
        self.iteration_history = []
        
    def iterative_retrieve(self, query: str, codebase_path: str, n_initial: int = 5, n_refine: int = 3) -> Dict[str, Any]:
        """
        Main entry point for iterative retrieval
        
        Args:
            query: User's question
            codebase_path: Path to indexed codebase
            n_initial: Number of chunks to retrieve initially
            n_refine: Number of chunks to retrieve in refinement rounds
            
        Returns:
            Dictionary with final results and iteration history
        """
        start_time = time.time()
        self.iteration_history = []
        
        # Initial retrieval
        logger.info(f"Starting initial retrieval for query: '{query}'")
        
        initial_results = self.retriever.retrieve(codebase_path, query, n_results=n_initial)
        
        if not initial_results:
            logger.warning("No initial results found")
            return {
                'final_context': [],
                'iterations': [],
                'query_evolution': [query],
                'time_seconds': time.time() - start_time
            }
        
        self.iteration_history.append({
            'iteration': 0,
            'query': query,
            'results': initial_results,
            'type': 'initial'
        })
        
        # Current working query and context
        current_query = query
        all_results = initial_results.copy()
        seen_chunk_ids = set([self._get_chunk_id(r) for r in initial_results])
        
        # Iterative refinement
        for i in range(self.max_iterations):
            iteration_num = i + 1
            logger.info(f"Starting refinement iteration {iteration_num}")
            
            # Analyze current results with LLM
            analysis = self._analyze_results(current_query, all_results, iteration_num)
            
            if analysis['is_satisfied']:
                logger.info(f"LLM satisfied after {iteration_num} iterations")
                break
            
            # Generate refined query
            refined_query = self._refine_query(current_query, analysis)
            logger.info(f"Refined query: '{refined_query}'")
            
            # Retrieve with refined query
            new_results = self.retriever.retrieve(codebase_path, refined_query, n_results=n_refine)
            
            # Filter out already seen chunks
            new_unique_results = []
            for r in new_results:
                chunk_id = self._get_chunk_id(r)
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    new_unique_results.append(r)
            
            if not new_unique_results:
                logger.info(f"No new unique results found in iteration {iteration_num}")
                break
            
            all_results.extend(new_unique_results)
            
            self.iteration_history.append({
                'iteration': iteration_num,
                'query': refined_query,
                'results': new_unique_results,
                'analysis': analysis,
                'type': 'refinement'
            })
            
            current_query = refined_query
        
        # Final ranking and deduplication
        final_context = self._rank_and_deduplicate(all_results)
        
        elapsed = time.time() - start_time
        logger.info(f"Completed {len(self.iteration_history)} iterations in {elapsed:.2f}s")
        
        return {
            'final_context': final_context,
            'iterations': self.iteration_history,
            'query_evolution': [h['query'] for h in self.iteration_history],
            'time_seconds': elapsed
        }
    
    def _analyze_results(self, query: str, results: List[Dict], iteration: int) -> Dict[str, Any]:
        """
        Use LLM to analyze retrieved results and identify gaps
        """
        # Build analysis prompt
        prompt = self._build_analysis_prompt(query, results, iteration)
        
        # Get LLM analysis
        analysis_response = self.llm.create_completion(
            prompt=prompt,
            max_tokens=300,
            temperature=0.3,
            stop=["</analysis>"]
        )
        
        # Parse response
        analysis_text = analysis_response['choices'][0]['text'].strip()
        
        # Extract structured info
        is_satisfied = "SATISFIED: YES" in analysis_text.upper()
        missing_aspects = self._extract_missing_aspects(analysis_text)
        suggested_keywords = self._extract_keywords(analysis_text)
        
        return {
            'is_satisfied': is_satisfied,
            'missing_aspects': missing_aspects,
            'suggested_keywords': suggested_keywords,
            'raw_analysis': analysis_text
        }
    
    def _build_analysis_prompt(self, query: str, results: List[Dict], iteration: int) -> str:
        """
        Build prompt for LLM to analyze retrieved code
        """
        # Format retrieved code chunks
        code_snippets = []
        for i, r in enumerate(results[:5]):  # Limit to 5 for analysis
            # Escape any triple backticks in the code
            safe_text = r['text'].replace('```', '\\`\\`\\`')
            code_snippets.append(
                f"\n--- CHUNK {i+1}: {r['file']} (lines {r['start_line']}-{r['end_line']}) ---\n"
                f"```python\n{safe_text}\n```\n"
            )
        
        code_context = "".join(code_snippets)
        
        prompt = f'''You are analyzing code search results for the query: "{query}"

Here are the code chunks found so far (iteration {iteration}):

{code_context}

Based on these results, please provide a structured analysis:

1. Are you satisfied that we have enough relevant code to answer the query? (SATISFIED: YES/NO)
2. What key aspects or concepts are still missing?
3. What specific keywords or phrases would help find missing information?

Format your response as:
SATISFIED: [YES/NO]
MISSING: [comma-separated list]
KEYWORDS: [comma-separated list]

Analysis:
'''
        return prompt
    
    def _refine_query(self, original_query: str, analysis: Dict) -> str:
        """
        Generate refined query based on analysis
        """
        if analysis['suggested_keywords']:
            keywords = " ".join(analysis['suggested_keywords'][:5])
            refined = f"{original_query} {keywords}"
        else:
            missing = analysis['missing_aspects'][0] if analysis['missing_aspects'] else ""
            refined = f"{original_query} related to {missing}" if missing else original_query
        return refined.strip()
    
    def _extract_missing_aspects(self, analysis_text: str) -> List[str]:
        """Extract missing aspects from analysis text"""
        match = re.search(r'MISSING:\s*(.*?)(?:\n|$)', analysis_text, re.IGNORECASE)
        if match:
            aspects = [a.strip() for a in match.group(1).split(',') if a.strip()]
            return aspects
        return []
    
    def _extract_keywords(self, analysis_text: str) -> List[str]:
        """Extract suggested keywords from analysis text"""
        match = re.search(r'KEYWORDS:\s*(.*?)(?:\n|$)', analysis_text, re.IGNORECASE)
        if match:
            keywords = [k.strip() for k in match.group(1).split(',') if k.strip()]
            return keywords
        return []
    
    def _get_chunk_id(self, chunk: Dict) -> str:
        """Generate unique ID for a chunk"""
        return f"{chunk['file']}:{chunk['start_line']}-{chunk['end_line']}"
    
    def _rank_and_deduplicate(self, results: List[Dict]) -> List[Dict]:
        """
        Rank and deduplicate final results
        """
        seen = set()
        unique = []
        sorted_results = sorted(results, key=lambda x: x.get('relevance', 0), reverse=True)
        
        for r in sorted_results:
            chunk_id = self._get_chunk_id(r)
            if chunk_id not in seen:
                seen.add(chunk_id)
                unique.append(r)
        return unique