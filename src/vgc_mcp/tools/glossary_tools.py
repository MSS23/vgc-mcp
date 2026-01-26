"""MCP tools for VGC glossary and term explanations."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.data.glossary_data import VGC_GLOSSARY
from vgc_mcp_core.utils.errors import api_error


def register_glossary_tools(mcp: FastMCP):
    """Register VGC glossary tools."""

    @mcp.tool()
    async def explain_vgc_term(term: str) -> dict:
        """
        Explain a VGC/Pokemon competitive term in simple language.
        
        Args:
            term: The term to explain (e.g., "EVs", "STAB", "OHKO", "Tailwind")
            
        Returns:
            Detailed explanation with examples and related terms
        """
        try:
            term_lower = term.lower().strip()
            
            # Try exact match first
            if term_lower in VGC_GLOSSARY:
                term_data = VGC_GLOSSARY[term_lower]
            else:
                # Try fuzzy matching
                found = False
                for key, data in VGC_GLOSSARY.items():
                    if term_lower in key or key in term_lower or term_lower in data["term"].lower():
                        term_data = data
                        found = True
                        break
                
                if not found:
                    # Suggest similar terms
                    suggestions = []
                    for key in VGC_GLOSSARY.keys():
                        if term_lower[0] == key[0] or any(c in key for c in term_lower[:3]):
                            suggestions.append(key)
                    
                    return {
                        "error": f"Term '{term}' not found in glossary",
                        "suggestions": suggestions[:5],
                        "available_terms": list(VGC_GLOSSARY.keys())[:20]
                    }
            
            # Build markdown output
            markdown_lines = [
                f"## Term: {term_data['term']}",
                "",
                f"### Simple Explanation",
                term_data["simple_explanation"],
                "",
                f"### Why It Matters",
                term_data["why_it_matters"],
                ""
            ]
            
            # Add common patterns
            if term_data.get("common_patterns"):
                markdown_lines.extend([
                    "### Common Patterns",
                    "| Pattern | Name | Use Case |",
                    "|---------|------|----------|"
                ])
                for pattern in term_data["common_patterns"]:
                    markdown_lines.append(
                        f"| {pattern['pattern']} | {pattern['name']} | {pattern['use_case']} |"
                    )
                markdown_lines.append("")
            
            # Add example
            if term_data.get("example"):
                markdown_lines.extend([
                    "### Example",
                    f'"{term_data["example"]}"',
                    ""
                ])
            
            # Add related terms
            if term_data.get("related_terms"):
                markdown_lines.append("### Related Terms")
                related = ", ".join([f"`{t}`" for t in term_data["related_terms"]])
                markdown_lines.append(related)
            
            response = {
                "term": term_data["term"],
                "simple_explanation": term_data["simple_explanation"],
                "why_it_matters": term_data["why_it_matters"],
                "common_patterns": term_data.get("common_patterns", []),
                "example": term_data.get("example"),
                "related_terms": term_data.get("related_terms", []),
                "markdown_summary": "\n".join(markdown_lines)
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in explain_vgc_term: {e}", exc_info=True)
            return api_error(str(e))
