#!/usr/bin/env python3
"""
Code Quality Metrics Analyzer for Memgraph
Connects to Memgraph, runs quality metrics queries, and outputs colored results
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import html

try:
    from neo4j import GraphDatabase
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
except ImportError:
    print("Missing required packages. Install with:")
    print("pip install neo4j rich")
    sys.exit(1)


class Severity(Enum):
    """Severity levels for metrics"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricResult:
    """Result of a single metric query"""
    name: str
    category: str
    value: Any
    severity: Severity
    threshold_info: str
    description: str
    query: str
    detailed_data: Optional[List[Dict[str, Any]]] = None  # Store detailed results


@dataclass
class CategorySummary:
    """Summary of a metric category"""
    category: str
    total_metrics: int
    excellent_count: int
    good_count: int
    acceptable_count: int
    warning_count: int
    critical_count: int
    overall_severity: Severity


class MemgraphAnalyzer:
    """Analyzer for code quality metrics in Memgraph"""
    
    SEVERITY_COLORS = {
        Severity.EXCELLENT: "bright_green",
        Severity.GOOD: "green",
        Severity.ACCEPTABLE: "yellow",
        Severity.WARNING: "orange1",
        Severity.CRITICAL: "red",
    }
    
    SEVERITY_EMOJIS = {
        Severity.EXCELLENT: "✨",
        Severity.GOOD: "✓",
        Severity.ACCEPTABLE: "⚠",
        Severity.WARNING: "⚠️",
        Severity.CRITICAL: "❌",
    }
    
    # Default patterns to exclude from dead code detection
    DEFAULT_EXCLUDE_PATTERNS = [
        'anonymous_',      # JS anonymous functions
        'arrow_',          # JS arrow functions
        'callback_',       # Generic callbacks
        'handler_',        # Event handlers
        'lambda_',         # Python lambdas
        '__anonymous',     # Various anonymous patterns
    ]
    
    # Default entry point patterns (never considered dead)
    DEFAULT_ENTRY_POINTS = [
        'main',
        '__init__',
        '__main__',
        'index',
        'default',
        'handler',
        'lambda_handler',  # AWS Lambda
        'run',
        'start',
        'init',
    ]
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 username: str = "", password: str = "",
                 project_graph_name: str = "",
                 exclude_patterns: Optional[List[str]] = None,
                 entry_points: Optional[List[str]] = None,
                 language: str = "javascript"):
        """Initialize connection to Memgraph
        
        Args:
            uri: Memgraph connection URI
            username: Memgraph username (optional)
            password: Memgraph password (optional)
            project_graph_name: Project node name in graph (filters all queries)
            exclude_patterns: Patterns to exclude from dead code detection
            entry_points: Function names that are entry points (never dead)
            language: Programming language for language-specific rules
        """
        self.console = Console()
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self.results: List[MetricResult] = []
        self.language = language.lower()
        self.project_graph_name = project_graph_name
        
        # Set exclude patterns
        if exclude_patterns is None:
            self.exclude_patterns = self.DEFAULT_EXCLUDE_PATTERNS.copy()
        else:
            self.exclude_patterns = exclude_patterns
        
        # Set entry points
        if entry_points is None:
            self.entry_points = self.DEFAULT_ENTRY_POINTS.copy()
        else:
            self.entry_points = entry_points
        
        # Add language-specific patterns
        if self.language == "javascript":
            self.exclude_patterns.extend([
                'anonymous_',
                'arrow_',
                'IIFE_',           # Immediately Invoked Function Expressions
                'closure_',
            ])
            self.entry_points.extend([
                'exports',
                'module.exports',
            ])
        
    def connect(self) -> bool:
        """Connect to Memgraph"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password) if self.username else None
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            self.console.print("✓ Connected to Memgraph", style="green")
            return True
        except Exception as e:
            self.console.print(f"✗ Failed to connect to Memgraph: {e}", style="red")
            return False
    
    def close(self):
        """Close connection"""
        if self.driver:
            self.driver.close()
    
    def run_query(self, query: str) -> List[Dict]:
        """Run a Cypher query and return results"""
        try:
            with self.driver.session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            self.console.print(f"Query error: {e}", style="red")
            return []
    
    def _get_project_filter(self, node_var: str = "n", node_type: str = "Module") -> str:
        """Generate project filter clause for queries
        
        Args:
            node_var: Variable name for the node to filter (e.g., 'm', 'f', 'c')
            node_type: Type of node (Module, Function, Class, etc.)
            
        Returns:
            Cypher WHERE clause or empty string if no project filter
        """
        if not self.project_graph_name:
            return ""
        
        # Map node types to their relationship paths from Project
        relationship_paths = {
            "Module": f"MATCH (p:Project {{name: '{self.project_graph_name}'}})-[:CONTAINS_MODULE]->({node_var})",
            "Package": f"MATCH (p:Project {{name: '{self.project_graph_name}'}})-[:CONTAINS_PACKAGE]->({node_var})",
            "Function": f"MATCH (p:Project {{name: '{self.project_graph_name}'}})-[:CONTAINS_MODULE|CONTAINS_PACKAGE*1..2]->(m)-[:DEFINES|DEFINES_METHOD]->({node_var})",
            "Method": f"MATCH (p:Project {{name: '{self.project_graph_name}'}})-[:CONTAINS_MODULE|CONTAINS_PACKAGE*1..2]->(m)-[:DEFINES]->(:Class)-[:DEFINES_METHOD]->({node_var})",
            "Class": f"MATCH (p:Project {{name: '{self.project_graph_name}'}})-[:CONTAINS_MODULE|CONTAINS_PACKAGE*1..2]->(m)-[:DEFINES]->({node_var})",
            "File": f"MATCH (p:Project {{name: '{self.project_graph_name}'}})-[:CONTAINS_FILE]->({node_var})",
            "Folder": f"MATCH (p:Project {{name: '{self.project_graph_name}'}})-[:CONTAINS_FOLDER]->({node_var})",
        }
        
        return relationship_paths.get(node_type, "")
    
    def analyze_cyclic_dependencies(self) -> List[MetricResult]:
        """Analyze cyclic dependencies"""
        results = []
        
        # Build project filter
        project_match = self._get_project_filter("m", "Module")
        project_clause = f"{project_match}\nWITH m\n" if project_match else ""
        
        # Count import cycles and get details
        query = f"""
        {project_clause}MATCH cycle = (m:Module)-[:IMPORTS*]->(m)
        WHERE length(cycle) > 1
        RETURN DISTINCT m.name as moduleName, 
               length(cycle) as cycleLength,
               id(m) as id
        LIMIT 100
        """
        cycle_data = self.run_query(query)
        cycle_count = len(cycle_data)
        
        # Get total count if needed
        if cycle_count == 100:
            count_query = f"""
            {project_clause}MATCH cycle = (m:Module)-[:IMPORTS*]->(m)
            WHERE length(cycle) > 1
            RETURN count(DISTINCT m) as cycleCount
            """
            count_data = self.run_query(count_query)
            cycle_count = count_data[0]['cycleCount'] if count_data else cycle_count
        
        if cycle_count == 0:
            severity = Severity.EXCELLENT
            threshold = "0 cycles (perfect)"
        elif cycle_count <= 2:
            severity = Severity.ACCEPTABLE
            threshold = "1-2 small cycles acceptable"
        elif cycle_count <= 5:
            severity = Severity.WARNING
            threshold = ">2 cycles is concerning"
        else:
            severity = Severity.CRITICAL
            threshold = ">5 cycles is critical"
        
        results.append(MetricResult(
            name="Import Cycles",
            category="Cyclic Dependencies",
            value=cycle_count,
            severity=severity,
            threshold_info=threshold,
            description="Modules involved in circular imports",
            query=query,
            detailed_data=cycle_data if cycle_data else None
        ))
        
        # Find max cycle length
        query = f"""
        {project_clause}MATCH cycle = (m:Module)-[:IMPORTS*]->(m)
        WHERE length(cycle) > 1
        RETURN max(length(cycle)) as maxCycleLength
        """
        data = self.run_query(query)
        max_length = data[0]['maxCycleLength'] if data and data[0]['maxCycleLength'] else 0
        
        if max_length == 0:
            severity = Severity.EXCELLENT
            threshold = "No cycles"
        elif max_length <= 3:
            severity = Severity.ACCEPTABLE
            threshold = "Cycles ≤3 hops are fixable"
        elif max_length <= 5:
            severity = Severity.WARNING
            threshold = "Cycles >3 are concerning"
        else:
            severity = Severity.CRITICAL
            threshold = "Long cycles (>5) are critical"
        
        results.append(MetricResult(
            name="Max Cycle Length",
            category="Cyclic Dependencies",
            value=max_length,
            severity=severity,
            threshold_info=threshold,
            description="Longest circular dependency chain",
            query=query
        ))
        
        # Inheritance cycles
        project_match_class = self._get_project_filter("c", "Class")
        project_clause_class = f"{project_match_class}\nWITH c\n" if project_match_class else ""
        
        query = f"""
        {project_clause_class}MATCH cycle = (c:Class)-[:INHERITS*]->(c)
        WHERE length(cycle) > 1
        RETURN DISTINCT c.name as className,
               length(cycle) as cycleLength,
               id(c) as id
        """
        inheritance_data = self.run_query(query)
        inheritance_cycles = len(inheritance_data)
        
        severity = Severity.EXCELLENT if inheritance_cycles == 0 else Severity.CRITICAL
        
        results.append(MetricResult(
            name="Inheritance Cycles",
            category="Cyclic Dependencies",
            value=inheritance_cycles,
            severity=severity,
            threshold_info="Must be 0 - inheritance cycles are bugs",
            description="Classes in circular inheritance",
            query=query,
            detailed_data=inheritance_data if inheritance_data else None
        ))
        
        return results
    
    def analyze_god_classes(self) -> List[MetricResult]:
        """Analyze God classes and modules"""
        results = []
        
        # God classes by method count - with details
        query = """
        MATCH (c:Class)-[:DEFINES_METHOD]->(m:Method)
        WITH c, count(m) as methodCount
        WHERE methodCount > 20
        RETURN c.name as className,
               methodCount,
               id(c) as id
        ORDER BY methodCount DESC
        LIMIT 50
        """
        god_class_data = self.run_query(query)
        god_count = len(god_class_data)
        max_methods = max([d['methodCount'] for d in god_class_data], default=0)
        
        # Get total count if we hit limit
        if god_count == 50:
            count_query = """
            MATCH (c:Class)-[:DEFINES_METHOD]->(m:Method)
            WITH c, count(m) as methodCount
            WHERE methodCount > 20
            RETURN count(c) as godClassCount, max(methodCount) as maxMethods
            """
            count_data = self.run_query(count_query)
            if count_data:
                god_count = count_data[0]['godClassCount']
                max_methods = count_data[0]['maxMethods'] if count_data[0]['maxMethods'] else max_methods
        
        if god_count == 0:
            severity = Severity.EXCELLENT
            threshold = "0 classes with >20 methods"
        elif god_count <= 2:
            severity = Severity.ACCEPTABLE
            threshold = "1-2 large classes acceptable"
        elif god_count <= 5:
            severity = Severity.WARNING
            threshold = ">2 God classes is concerning"
        else:
            severity = Severity.CRITICAL
            threshold = ">5 God classes is critical"
        
        results.append(MetricResult(
            name="God Classes (>20 methods)",
            category="God Classes/Modules",
            value=f"{god_count} classes (max: {max_methods} methods)",
            severity=severity,
            threshold_info=threshold,
            description="Classes with excessive methods",
            query=query,
            detailed_data=god_class_data if god_class_data else None
        ))
        
        # God modules by definition count - with details
        query = """
        MATCH (mod:Module)-[:DEFINES]->(entity)
        WHERE entity:Function OR entity:Class
        WITH mod, count(entity) as definitionCount
        WHERE definitionCount > 30
        RETURN mod.name as moduleName,
               definitionCount,
               id(mod) as id
        ORDER BY definitionCount DESC
        LIMIT 50
        """
        god_module_data = self.run_query(query)
        mod_count = len(god_module_data)
        max_defs = max([d['definitionCount'] for d in god_module_data], default=0)
        
        if mod_count == 0:
            severity = Severity.EXCELLENT
            threshold = "0 modules with >30 definitions"
        elif mod_count <= 2:
            severity = Severity.ACCEPTABLE
            threshold = "1-2 large modules acceptable"
        else:
            severity = Severity.CRITICAL
            threshold = ">2 God modules is critical"
        
        results.append(MetricResult(
            name="God Modules (>30 definitions)",
            category="God Classes/Modules",
            value=f"{mod_count} modules (max: {max_defs} definitions)",
            severity=severity,
            threshold_info=threshold,
            description="Modules defining too many entities",
            query=query,
            detailed_data=god_module_data if god_module_data else None
        ))
        
        # Hub functions (high fan-in) - with details
        query = """
        MATCH (f:Function)<-[:CALLS]-(caller:Function)
        WITH f, count(DISTINCT caller) as callerCount
        WHERE callerCount > 20
        RETURN f.name as functionName,
               callerCount,
               id(f) as id
        ORDER BY callerCount DESC
        LIMIT 50
        """
        hub_data = self.run_query(query)
        hub_count = len(hub_data)
        max_callers = max([d['callerCount'] for d in hub_data], default=0)
        
        if hub_count == 0:
            severity = Severity.GOOD
            threshold = "0-5 high fan-in functions is good"
        elif hub_count <= 5:
            severity = Severity.ACCEPTABLE
            threshold = "Some hub functions are OK if stable"
        else:
            severity = Severity.WARNING
            threshold = ">5 hub functions is risky"
        
        results.append(MetricResult(
            name="Hub Functions (>20 callers)",
            category="God Classes/Modules",
            value=f"{hub_count} functions (max: {max_callers} callers)",
            severity=severity,
            threshold_info=threshold,
            description="Functions called by many others",
            query=query,
            detailed_data=hub_data if hub_data else None
        ))
        
        return results
    
    def analyze_inheritance(self) -> List[MetricResult]:
        """Analyze inheritance quality"""
        results = []
        
        # Max inheritance depth
        query = """
        MATCH path = (c:Class)-[:INHERITS*]->(base:Class)
        WHERE NOT (base)-[:INHERITS]->()
        RETURN max(length(path)) as maxDepth, avg(length(path)) as avgDepth
        """
        data = self.run_query(query)
        max_depth = data[0]['maxDepth'] if data and data[0]['maxDepth'] else 0
        avg_depth = data[0]['avgDepth'] if data and data[0]['avgDepth'] else 0
        
        if max_depth == 0:
            severity = Severity.EXCELLENT
            threshold = "No inheritance or flat hierarchies"
        elif max_depth <= 3:
            severity = Severity.GOOD
            threshold = "Depth ≤3 is good"
        elif max_depth <= 5:
            severity = Severity.ACCEPTABLE
            threshold = "Depth 4-5 is acceptable"
        else:
            severity = Severity.CRITICAL
            threshold = "Depth >5 is critical (4x more bugs)"
        
        results.append(MetricResult(
            name="Max Inheritance Depth",
            category="Inheritance Quality",
            value=f"{max_depth} levels (avg: {avg_depth:.1f})" if avg_depth else f"{max_depth} levels",
            severity=severity,
            threshold_info=threshold,
            description="Longest inheritance chain",
            query=query
        ))
        
        # Multiple inheritance
        query = """
        MATCH (c:Class)-[:INHERITS]->(parent:Class)
        WITH c, count(parent) as parentCount
        WHERE parentCount > 1
        RETURN count(c) as multipleInheritanceCount
        """
        data = self.run_query(query)
        multi_count = data[0]['multipleInheritanceCount'] if data else 0
        
        if multi_count == 0:
            severity = Severity.EXCELLENT
            threshold = "0 multiple inheritance (best practice)"
        elif multi_count <= 2:
            severity = Severity.ACCEPTABLE
            threshold = "Minimal multiple inheritance"
        else:
            severity = Severity.WARNING
            threshold = "Multiple inheritance increases complexity"
        
        results.append(MetricResult(
            name="Multiple Inheritance",
            category="Inheritance Quality",
            value=f"{multi_count} classes",
            severity=severity,
            threshold_info=threshold,
            description="Classes inheriting from multiple parents",
            query=query
        ))
        
        return results
    
    def analyze_dead_code(self) -> List[MetricResult]:
        """Analyze dead code"""
        results = []
        
        # Build WHERE clause to exclude patterns
        exclude_conditions = []
        for pattern in self.exclude_patterns:
            exclude_conditions.append(f"NOT f.name STARTS WITH '{pattern}'")
        
        # Build WHERE clause for entry points
        entry_point_conditions = ", ".join([f"'{ep}'" for ep in self.entry_points])
        
        # Uncalled functions (with exclusions) - with detailed data
        # Excludes nested functions to avoid false positives from closures/decorators
        query = f"""
        MATCH (f:Function)
        WHERE NOT (f)<-[:CALLS]-()
        AND NOT (f)<-[:DEFINES]-(:Function)
        AND NOT f.name IN [{entry_point_conditions}]
        AND NOT f.name STARTS WITH 'test_'
        AND NOT f.name STARTS WITH '_test'
        AND {' AND '.join(exclude_conditions)}
        RETURN f.name as functionName, 
               labels(f) as labels,
               id(f) as id
        LIMIT 500
        """
        dead_functions_data = self.run_query(query)
        dead_count = len(dead_functions_data)
        
        # Get total count if we hit the limit
        if dead_count == 500:
            count_query = f"""
            MATCH (f:Function)
            WHERE NOT (f)<-[:CALLS]-()
            AND NOT (f)<-[:DEFINES]-(:Function)
            AND NOT f.name IN [{entry_point_conditions}]
            AND NOT f.name STARTS WITH 'test_'
            AND NOT f.name STARTS WITH '_test'
            AND {' AND '.join(exclude_conditions)}
            RETURN count(f) as total
            """
            count_data = self.run_query(count_query)
            dead_count = count_data[0]['total'] if count_data else dead_count
        
        # Get total functions (excluding anonymous)
        total_query = f"""
        MATCH (f:Function)
        WHERE {' AND '.join(exclude_conditions)}
        RETURN count(f) as total
        """
        total_data = self.run_query(total_query)
        total = total_data[0]['total'] if total_data else 1
        dead_pct = (dead_count / total * 100) if total > 0 else 0
        
        if dead_pct < 5:
            severity = Severity.EXCELLENT
            threshold = "<5% dead code"
        elif dead_pct < 15:
            severity = Severity.GOOD
            threshold = "5-15% dead code"
        elif dead_pct < 25:
            severity = Severity.ACCEPTABLE
            threshold = "15-25% dead code"
        else:
            severity = Severity.WARNING
            threshold = ">25% dead code is wasteful"
        
        results.append(MetricResult(
            name="Potentially Dead Functions",
            category="Dead Code",
            value=f"{dead_count} ({dead_pct:.1f}%) [excluding anonymous]",
            severity=severity,
            threshold_info=threshold,
            description=f"Functions never called (excludes nested functions, tests, and patterns: {', '.join(self.exclude_patterns[:3])}...)",
            query=query,
            detailed_data=dead_functions_data[:100] if dead_functions_data else None  # Limit to 100 for display
        ))
        
        # Count excluded functions for reference
        excluded_query = f"""
        MATCH (f:Function)
        WHERE ({' OR '.join([f"f.name STARTS WITH '{p}'" for p in self.exclude_patterns])})
        RETURN count(f) as excludedCount
        """
        excluded_data = self.run_query(excluded_query)
        excluded_count = excluded_data[0]['excludedCount'] if excluded_data else 0
        
        if excluded_count > 0:
            results.append(MetricResult(
                name="Anonymous/Callback Functions",
                category="Dead Code",
                value=f"{excluded_count} functions (excluded from dead code check)",
                severity=Severity.EXCELLENT,
                threshold_info="Excluded as likely false positives",
                description="Functions matching exclusion patterns (callbacks, anonymous, etc.)",
                query=excluded_query
            ))
        
        # Unimported modules - with detailed data
        query = """
        MATCH (m:Module)
        WHERE NOT (m)<-[:IMPORTS]-()
        AND NOT m.name CONTAINS '__init__'
        AND NOT m.name CONTAINS 'index'
        RETURN m.name as moduleName,
               id(m) as id
        """
        orphan_data = self.run_query(query)
        orphan_count = len(orphan_data)
        
        if orphan_count == 0:
            severity = Severity.EXCELLENT
            threshold = "0 orphaned modules"
        elif orphan_count <= 2:
            severity = Severity.GOOD
            threshold = "1-2 entry point modules OK"
        else:
            severity = Severity.WARNING
            threshold = ">2 orphaned modules suspicious"
        
        results.append(MetricResult(
            name="Orphaned Modules",
            category="Dead Code",
            value=f"{orphan_count} modules",
            severity=severity,
            threshold_info=threshold,
            description="Modules never imported by others (entry points excluded)",
            query=query,
            detailed_data=orphan_data if orphan_data else None
        ))
        
        return results
    
    def analyze_coupling_cohesion(self) -> List[MetricResult]:
        """Analyze coupling and cohesion"""
        results = []
        
        # Average instability
        query = """
        MATCH (m:Module)
        OPTIONAL MATCH (m)-[:IMPORTS]->(dependency:Module)
        OPTIONAL MATCH (m)<-[:IMPORTS]-(dependent:Module)
        WITH m, 
             count(DISTINCT dependency) as ce,
             count(DISTINCT dependent) as ca
        WHERE ce + ca > 0
        WITH toFloat(ce) / (ce + ca) as instability
        RETURN avg(instability) as avgInstability, max(instability) as maxInstability
        """
        data = self.run_query(query)
        avg_inst = data[0]['avgInstability'] if data and data[0]['avgInstability'] else 0
        max_inst = data[0]['maxInstability'] if data and data[0]['maxInstability'] else 0
        
        if avg_inst < 0.3:
            severity = Severity.EXCELLENT
            threshold = "Avg instability <0.3 is excellent"
        elif avg_inst < 0.5:
            severity = Severity.GOOD
            threshold = "Avg instability <0.5 is good"
        elif avg_inst < 0.7:
            severity = Severity.ACCEPTABLE
            threshold = "Avg instability <0.7 is acceptable"
        else:
            severity = Severity.WARNING
            threshold = "Avg instability >0.7 indicates high coupling"
        
        results.append(MetricResult(
            name="Average Module Instability",
            category="Coupling & Cohesion",
            value=f"{avg_inst:.2f} (max: {max_inst:.2f})",
            severity=severity,
            threshold_info=threshold,
            description="I = Ce/(Ce+Ca) - measures module stability",
            query=query
        ))
        
        # Modules with poor cohesion
        query = """
        MATCH (m:Module)-[:DEFINES]->(f:Function)
        OPTIONAL MATCH (f)-[:CALLS]->(internal:Function)<-[:DEFINES]-(m)
        OPTIONAL MATCH (f)-[:CALLS]->(external:Function)<-[:DEFINES]-(otherMod:Module)
        WHERE otherMod <> m
        WITH m, 
             count(DISTINCT internal) as internalCalls,
             count(DISTINCT external) as externalCalls
        WHERE internalCalls + externalCalls > 0
        WITH CASE WHEN externalCalls > 0 
                  THEN toFloat(internalCalls) / externalCalls 
                  ELSE internalCalls 
             END as cohesionRatio
        WHERE cohesionRatio < 1.0
        RETURN count(*) as lowCohesionCount
        """
        data = self.run_query(query)
        low_cohesion = data[0]['lowCohesionCount'] if data else 0
        
        # Get total modules
        total_query = "MATCH (m:Module) RETURN count(m) as total"
        total_data = self.run_query(total_query)
        total = total_data[0]['total'] if total_data else 1
        low_cohesion_pct = (low_cohesion / total * 100) if total > 0 else 0
        
        if low_cohesion_pct < 10:
            severity = Severity.EXCELLENT
            threshold = "<10% low cohesion modules"
        elif low_cohesion_pct < 25:
            severity = Severity.GOOD
            threshold = "10-25% low cohesion"
        elif low_cohesion_pct < 40:
            severity = Severity.ACCEPTABLE
            threshold = "25-40% low cohesion"
        else:
            severity = Severity.WARNING
            threshold = ">40% low cohesion is concerning"
        
        results.append(MetricResult(
            name="Low Cohesion Modules",
            category="Coupling & Cohesion",
            value=f"{low_cohesion} ({low_cohesion_pct:.1f}%)",
            severity=severity,
            threshold_info=threshold,
            description="Modules with more external than internal calls",
            query=query
        ))
        
        return results
    
    def analyze_size_distribution(self) -> List[MetricResult]:
        """Analyze size distributions"""
        results = []
        
        # Average methods per class
        query = """
        MATCH (c:Class)-[:DEFINES_METHOD]->(m:Method)
        WITH c, count(m) as methodCount
        RETURN avg(methodCount) as avgMethods, max(methodCount) as maxMethods
        """
        data = self.run_query(query)
        avg_methods = data[0]['avgMethods'] if data and data[0]['avgMethods'] else 0
        max_methods = data[0]['maxMethods'] if data and data[0]['maxMethods'] else 0
        
        if avg_methods < 10:
            severity = Severity.EXCELLENT
            threshold = "Avg <10 methods per class"
        elif avg_methods < 15:
            severity = Severity.GOOD
            threshold = "Avg 10-15 methods"
        elif avg_methods < 20:
            severity = Severity.ACCEPTABLE
            threshold = "Avg 15-20 methods"
        else:
            severity = Severity.WARNING
            threshold = "Avg >20 methods is too high"
        
        results.append(MetricResult(
            name="Avg Methods per Class",
            category="Size Distribution",
            value=f"{avg_methods:.1f} (max: {max_methods})" if avg_methods else "N/A",
            severity=severity,
            threshold_info=threshold,
            description="Average class size",
            query=query
        ))
        
        # Folder nesting depth
        query = """
        MATCH path = (p:Project)-[:CONTAINS_FOLDER*]->(f:Folder)
        WHERE NOT (f)-[:CONTAINS_FOLDER]->()
        WITH length(path) as depth
        RETURN max(depth) as maxDepth, avg(depth) as avgDepth
        """
        data = self.run_query(query)
        max_depth = data[0]['maxDepth'] if data and data[0]['maxDepth'] else 0
        avg_depth = data[0]['avgDepth'] if data and data[0]['avgDepth'] else 0
        
        if max_depth <= 3:
            severity = Severity.EXCELLENT
            threshold = "Max depth ≤3 is excellent"
        elif max_depth <= 6:
            severity = Severity.GOOD
            threshold = "Max depth 4-6 is good"
        elif max_depth <= 10:
            severity = Severity.ACCEPTABLE
            threshold = "Max depth 7-10 is acceptable"
        else:
            severity = Severity.WARNING
            threshold = "Max depth >10 is over-nested"
        
        results.append(MetricResult(
            name="Folder Nesting Depth",
            category="Size Distribution",
            value=f"Max: {max_depth}, Avg: {avg_depth:.1f}" if avg_depth else f"Max: {max_depth}",
            severity=severity,
            threshold_info=threshold,
            description="Directory structure depth",
            query=query
        ))
        
        return results
    
    def analyze_documentation(self) -> List[MetricResult]:
        """Analyze documentation coverage"""
        results = []
        
        # Overall documentation coverage
        query = """
        MATCH (n)
        WHERE n:Function OR n:Class OR n:Method
        WITH count(n) as total,
             sum(CASE WHEN n.docstring IS NOT NULL AND n.docstring <> "" 
                      THEN 1 ELSE 0 END) as documented
        RETURN total, documented, 
               toFloat(documented) / total * 100 as coverage
        """
        data = self.run_query(query)
        
        if data and data[0]['total'] > 0:
            coverage = data[0]['coverage']
            total = data[0]['total']
            documented = data[0]['documented']
            undocumented = total - documented
            
            if coverage >= 80:
                severity = Severity.EXCELLENT
                threshold = "≥80% is excellent"
            elif coverage >= 60:
                severity = Severity.GOOD
                threshold = "60-80% is good"
            elif coverage >= 40:
                severity = Severity.ACCEPTABLE
                threshold = "40-60% is acceptable"
            elif coverage >= 20:
                severity = Severity.WARNING
                threshold = "20-40% needs improvement"
            else:
                severity = Severity.CRITICAL
                threshold = "<20% is critical"
            
            results.append(MetricResult(
                name="Overall Documentation Coverage",
                category="Documentation Quality",
                value=f"{coverage:.1f}% ({documented}/{total})",
                severity=severity,
                threshold_info=threshold,
                description="Percentage of functions/classes/methods with docstrings",
                query=query
            ))
        
        # Coverage by entity type
        query = """
        MATCH (n)
        WHERE n:Function OR n:Class OR n:Method OR n:Module
        WITH labels(n)[0] as entityType, n
        WITH entityType,
             count(n) as total,
             sum(CASE WHEN n.docstring IS NOT NULL AND n.docstring <> "" 
                      THEN 1 ELSE 0 END) as documented
        RETURN entityType,
               total,
               documented,
               toFloat(documented) / total * 100 as coverage
        ORDER BY coverage ASC
        """
        type_data = self.run_query(query)
        
        if type_data:
            # Find the worst documented type
            worst_type = type_data[0]
            worst_coverage = worst_type['coverage']
            
            coverage_details = []
            for item in type_data:
                coverage_details.append({
                    'entityType': item['entityType'],
                    'total': item['total'],
                    'documented': item['documented'],
                    'coverage': f"{item['coverage']:.1f}%"
                })
            
            if worst_coverage >= 70:
                severity = Severity.GOOD
                threshold = "All types well documented"
            elif worst_coverage >= 50:
                severity = Severity.ACCEPTABLE
                threshold = "Some types need improvement"
            elif worst_coverage >= 30:
                severity = Severity.WARNING
                threshold = "Poor coverage on some types"
            else:
                severity = Severity.CRITICAL
                threshold = "Critical gaps in documentation"
            
            results.append(MetricResult(
                name="Documentation by Type",
                category="Documentation Quality",
                value=f"Worst: {worst_type['entityType']} at {worst_coverage:.1f}%",
                severity=severity,
                threshold_info=threshold,
                description="Documentation coverage breakdown by entity type",
                query=query,
                detailed_data=coverage_details
            ))
        
        # Undocumented public functions (high priority)
        query = """
        MATCH (f:Function)<-[:CALLS]-(caller)
        WHERE (f.docstring IS NULL OR f.docstring = "")
          AND NOT f.name STARTS WITH '_'
          AND NOT f.name STARTS WITH 'anonymous_'
          AND NOT f.name STARTS WITH 'arrow_'
          AND NOT f.name STARTS WITH 'callback_'
        WITH f, count(DISTINCT caller) as callerCount
        WHERE callerCount >= 3
        RETURN f.name as functionName,
               callerCount as timesUsed,
               id(f) as id
        ORDER BY callerCount DESC
        LIMIT 50
        """
        public_data = self.run_query(query)
        public_count = len(public_data)
        
        if public_count == 0:
            severity = Severity.EXCELLENT
            threshold = "All public APIs documented"
        elif public_count <= 5:
            severity = Severity.GOOD
            threshold = "Few undocumented public APIs"
        elif public_count <= 15:
            severity = Severity.ACCEPTABLE
            threshold = "Some undocumented public APIs"
        elif public_count <= 30:
            severity = Severity.WARNING
            threshold = "Many undocumented public APIs"
        else:
            severity = Severity.CRITICAL
            threshold = "Critical: extensive undocumented public APIs"
        
        max_usage = max([d['timesUsed'] for d in public_data], default=0)
        
        results.append(MetricResult(
            name="Undocumented Public APIs",
            category="Documentation Quality",
            value=f"{public_count} functions (max usage: {max_usage}x)",
            severity=severity,
            threshold_info=threshold,
            description="Public functions (≥3 callers) without docstrings",
            query=query,
            detailed_data=public_data if public_data else None
        ))
        
        # Poor quality docstrings (too short)
        query = """
        MATCH (n)
        WHERE (n:Function OR n:Class OR n:Method)
          AND n.docstring IS NOT NULL 
          AND n.docstring <> ""
          AND size(n.docstring) < 30
        RETURN labels(n)[0] as entityType,
               n.name as name,
               size(n.docstring) as length,
               id(n) as id
        ORDER BY length ASC
        LIMIT 50
        """
        short_data = self.run_query(query)
        short_count = len(short_data)
        
        if short_count == 0:
            severity = Severity.EXCELLENT
            threshold = "No short docstrings found"
        elif short_count <= 10:
            severity = Severity.GOOD
            threshold = "Few short docstrings"
        elif short_count <= 25:
            severity = Severity.ACCEPTABLE
            threshold = "Some short docstrings"
        else:
            severity = Severity.WARNING
            threshold = "Many low-quality docstrings"
        
        avg_length = sum([d['length'] for d in short_data]) / len(short_data) if short_data else 0
        
        results.append(MetricResult(
            name="Low Quality Docstrings",
            category="Documentation Quality",
            value=f"{short_count} docstrings (avg: {avg_length:.0f} chars)",
            severity=severity,
            threshold_info=threshold,
            description="Docstrings shorter than 30 characters",
            query=query,
            detailed_data=short_data if short_data else None
        ))
        
        return results
    
    def analyze_graph_connectivity(self) -> List[MetricResult]:
        """Analyze graph-wide properties"""
        results = []
        
        # Graph density
        query = """
        MATCH (m:Module)
        WITH count(m) as nodeCount
        MATCH ()-[r:IMPORTS]->()
        WITH nodeCount, count(r) as edgeCount
        WHERE nodeCount > 1
        RETURN toFloat(edgeCount) / (nodeCount * (nodeCount - 1)) as density
        """
        data = self.run_query(query)
        density = data[0]['density'] if data and data[0]['density'] else 0
        
        if density < 0.05:
            severity = Severity.EXCELLENT
            threshold = "Density <0.05 is excellent"
        elif density < 0.10:
            severity = Severity.GOOD
            threshold = "Density 0.05-0.10 is good"
        elif density < 0.20:
            severity = Severity.ACCEPTABLE
            threshold = "Density 0.10-0.20 is acceptable"
        else:
            severity = Severity.WARNING
            threshold = "Density >0.20 is too coupled"
        
        results.append(MetricResult(
            name="Module Graph Density",
            category="Graph Connectivity",
            value=f"{density:.4f}",
            severity=severity,
            threshold_info=threshold,
            description="How connected modules are (edges/possible edges)",
            query=query
        ))
        
        # Isolated modules
        query = """
        MATCH (m:Module)
        WHERE NOT (m)-[:IMPORTS]->() AND NOT (m)<-[:IMPORTS]-()
        RETURN count(m) as isolatedCount
        """
        data = self.run_query(query)
        isolated = data[0]['isolatedCount'] if data else 0
        
        if isolated == 0:
            severity = Severity.EXCELLENT
            threshold = "0 isolated modules"
        elif isolated <= 2:
            severity = Severity.GOOD
            threshold = "1-2 isolated modules OK"
        else:
            severity = Severity.WARNING
            threshold = ">2 isolated modules suspicious"
        
        results.append(MetricResult(
            name="Isolated Modules",
            category="Graph Connectivity",
            value=f"{isolated} modules",
            severity=severity,
            threshold_info=threshold,
            description="Modules with no imports or importers",
            query=query
        ))
        
        return results
    
    def calculate_overall_score(self) -> Tuple[float, Severity]:
        """Calculate overall quality score (0-100)"""
        if not self.results:
            return 0.0, Severity.CRITICAL
        
        severity_scores = {
            Severity.EXCELLENT: 100,
            Severity.GOOD: 80,
            Severity.ACCEPTABLE: 60,
            Severity.WARNING: 40,
            Severity.CRITICAL: 20,
        }
        
        total_score = sum(severity_scores[r.severity] for r in self.results)
        avg_score = total_score / len(self.results)
        
        if avg_score >= 90:
            overall = Severity.EXCELLENT
        elif avg_score >= 75:
            overall = Severity.GOOD
        elif avg_score >= 60:
            overall = Severity.ACCEPTABLE
        elif avg_score >= 40:
            overall = Severity.WARNING
        else:
            overall = Severity.CRITICAL
        
        return avg_score, overall
    
    def get_category_summary(self, category: str) -> CategorySummary:
        """Get summary for a category"""
        cat_results = [r for r in self.results if r.category == category]
        
        counts = {s: 0 for s in Severity}
        for result in cat_results:
            counts[result.severity] += 1
        
        # Overall severity is the worst severity in the category
        if counts[Severity.CRITICAL] > 0:
            overall = Severity.CRITICAL
        elif counts[Severity.WARNING] > 0:
            overall = Severity.WARNING
        elif counts[Severity.ACCEPTABLE] > 0:
            overall = Severity.ACCEPTABLE
        elif counts[Severity.GOOD] > 0:
            overall = Severity.GOOD
        else:
            overall = Severity.EXCELLENT
        
        return CategorySummary(
            category=category,
            total_metrics=len(cat_results),
            excellent_count=counts[Severity.EXCELLENT],
            good_count=counts[Severity.GOOD],
            acceptable_count=counts[Severity.ACCEPTABLE],
            warning_count=counts[Severity.WARNING],
            critical_count=counts[Severity.CRITICAL],
            overall_severity=overall
        )
    
    def run_all_analyses(self):
        """Run all quality analyses"""
        self.console.print("\n[bold cyan]Running Code Quality Analysis...[/bold cyan]\n")
        
        analyses = [
            ("Cyclic Dependencies", self.analyze_cyclic_dependencies),
            ("God Classes/Modules", self.analyze_god_classes),
            ("Inheritance Quality", self.analyze_inheritance),
            ("Dead Code", self.analyze_dead_code),
            ("Coupling & Cohesion", self.analyze_coupling_cohesion),
            ("Size Distribution", self.analyze_size_distribution),
            ("Documentation Quality", self.analyze_documentation),
            ("Graph Connectivity", self.analyze_graph_connectivity),
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            for name, func in analyses:
                task = progress.add_task(f"Analyzing {name}...", total=None)
                results = func()
                self.results.extend(results)
                progress.remove_task(task)
        
        self.console.print(f"✓ Analysis complete: {len(self.results)} metrics evaluated\n", 
                          style="green")
    
    def print_summary(self):
        """Print colored summary to console"""
        self.console.print("\n" + "="*80, style="bold")
        self.console.print("CODE QUALITY ANALYSIS SUMMARY", style="bold cyan", justify="center")
        self.console.print("="*80 + "\n", style="bold")
        
        # Overall score
        overall_score, overall_severity = self.calculate_overall_score()
        color = self.SEVERITY_COLORS[overall_severity]
        emoji = self.SEVERITY_EMOJIS[overall_severity]
        
        score_panel = Panel(
            f"[bold {color}]{emoji} Overall Quality Score: {overall_score:.1f}/100[/bold {color}]\n"
            f"[{color}]Status: {overall_severity.value.upper()}[/{color}]",
            title="[bold]Overall Assessment[/bold]",
            border_style=color,
            box=box.DOUBLE
        )
        self.console.print(score_panel)
        self.console.print()
        
        # Category summaries
        categories = list(set(r.category for r in self.results))
        
        for category in categories:
            summary = self.get_category_summary(category)
            color = self.SEVERITY_COLORS[summary.overall_severity]
            emoji = self.SEVERITY_EMOJIS[summary.overall_severity]
            
            table = Table(
                title=f"{emoji} {category}",
                title_style=f"bold {color}",
                border_style=color,
                box=box.ROUNDED
            )
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")
            table.add_column("Status", justify="center")
            table.add_column("Threshold", style="dim")
            
            cat_results = [r for r in self.results if r.category == category]
            for result in cat_results:
                r_color = self.SEVERITY_COLORS[result.severity]
                r_emoji = self.SEVERITY_EMOJIS[result.severity]
                
                table.add_row(
                    result.name,
                    str(result.value),
                    f"[{r_color}]{r_emoji} {result.severity.value}[/{r_color}]",
                    result.threshold_info
                )
            
            self.console.print(table)
            self.console.print()
        
        # Critical issues
        critical_results = [r for r in self.results if r.severity == Severity.CRITICAL]
        if critical_results:
            self.console.print(Panel(
                "[bold red]⚠️  CRITICAL ISSUES FOUND ⚠️[/bold red]\n\n" +
                "\n".join(f"• {r.category}: {r.name} = {r.value}" 
                         for r in critical_results),
                title="[bold red]Action Required[/bold red]",
                border_style="red",
                box=box.HEAVY
            ))
        
        # Recommendations
        self.print_recommendations()
    
    def print_recommendations(self):
        """Print actionable recommendations"""
        recommendations = []
        
        # Check for cycles
        cycle_results = [r for r in self.results 
                        if r.category == "Cyclic Dependencies" 
                        and r.severity in [Severity.WARNING, Severity.CRITICAL]]
        if cycle_results:
            recommendations.append(
                "🔴 PRIORITY 1: Break circular dependencies - they are architectural cancer"
            )
        
        # Check for God classes
        god_results = [r for r in self.results 
                      if r.category == "God Classes/Modules" 
                      and r.severity in [Severity.WARNING, Severity.CRITICAL]]
        if god_results:
            recommendations.append(
                "🟡 PRIORITY 2: Refactor God classes/modules - split by responsibility"
            )
        
        # Check for dead code
        dead_results = [r for r in self.results 
                       if r.category == "Dead Code" 
                       and r.name == "Potentially Dead Functions"]
        if dead_results and dead_results[0].severity in [Severity.WARNING, Severity.ACCEPTABLE]:
            recommendations.append(
                "🟢 QUICK WIN: Remove dead code - easy cleanup with immediate benefits"
            )
        
        # Check for inheritance issues
        inh_results = [r for r in self.results 
                      if r.category == "Inheritance Quality" 
                      and r.severity in [Severity.WARNING, Severity.CRITICAL]]
        if inh_results:
            recommendations.append(
                "🟡 PRIORITY 3: Flatten deep inheritance - favor composition over inheritance"
            )
        
        if recommendations:
            self.console.print("\n")
            rec_panel = Panel(
                "\n".join(f"{i+1}. {rec}" for i, rec in enumerate(recommendations)),
                title="[bold cyan]📋 Recommended Actions[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED
            )
            self.console.print(rec_panel)
    
    def export_to_json(self, filename: str = "quality_report.json"):
        """Export results to JSON file"""
        overall_score, overall_severity = self.calculate_overall_score()
        
        # Get category summaries
        categories = list(set(r.category for r in self.results))
        category_summaries = {
            cat: asdict(self.get_category_summary(cat))
            for cat in categories
        }
        
        # Convert enum to string for JSON serialization
        for cat_data in category_summaries.values():
            cat_data['overall_severity'] = cat_data['overall_severity'].value
        
        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "memgraph_uri": self.uri,
                "total_metrics_evaluated": len(self.results),
                "language": self.language,
                "exclude_patterns": self.exclude_patterns,
                "entry_points": self.entry_points,
            },
            "overall_assessment": {
                "score": round(overall_score, 2),
                "severity": overall_severity.value,
            },
            "category_summaries": category_summaries,
            "detailed_metrics": [
                {
                    "name": r.name,
                    "category": r.category,
                    "value": str(r.value),
                    "severity": r.severity.value,
                    "threshold_info": r.threshold_info,
                    "description": r.description,
                    "query": r.query
                }
                for r in self.results
            ],
            "critical_issues": [
                {
                    "category": r.category,
                    "name": r.name,
                    "value": str(r.value),
                    "description": r.description
                }
                for r in self.results if r.severity == Severity.CRITICAL
            ],
            "recommendations": self._generate_recommendations()
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.console.print(f"\n✓ Report exported to [cyan]{filename}[/cyan]", style="green")
    
    def _normalize_project_name(self, project_name: str) -> str:
        """Convert project name to lowercase with dashes"""
        return project_name.lower().replace(" ", "-").replace("_", "-")
    
    def export_project_file(self, project_name: str, output_path: str, repo_link: str = ""):
        """
        Export project metadata to outputs/[project-name]/project.json
        
        Args:
            output_path: Path to project output directory (e.g., outputs/my-project)
        """
        import os
        
        # output_path is already outputs/[project-name]
        os.makedirs(output_path, exist_ok=True)
        
        # Normalize project name for ID
        normalized_name = self._normalize_project_name(project_name)
        filename = os.path.join(output_path, "project.json")
        
        # Calculate overall score
        overall_score, overall_severity = self.calculate_overall_score()
        
        # Build project data
        project_data = {
            "id": normalized_name,
            "name": project_name,
            "repoLink": repo_link if repo_link else "",
            "description": f"{project_name} code quality metrics",
            "overallScore": int(round(overall_score)),
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(project_data, f, indent=2)
        
        self.console.print(f"✓ Project metadata exported to [cyan]{filename}[/cyan]", style="green")
        return filename
    
    def export_metrics_file(self, project_name: str, output_path: str):
        """
        Export metrics file to outputs/[project-name]/metrics/[date-stamp].json
        
        Args:
            project_name: Name of the project
            output_path: Path to project output directory (e.g., outputs/my-project)
        """
        import os
        
        overall_score, overall_severity = self.calculate_overall_score()
        
        # Normalize project name for project ID
        normalized_name = self._normalize_project_name(project_name)
        
        # Create metrics subdirectory
        metrics_dir = os.path.join(output_path, "metrics")
        os.makedirs(metrics_dir, exist_ok=True)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        filename = os.path.join(metrics_dir, f"{timestamp}.json")
        
        # Calculate severity distribution
        severity_counts = {
            "excellent": 0,
            "good": 0,
            "acceptable": 0,
            "warning": 0,
            "critical": 0
        }
        
        for r in self.results:
            severity_counts[r.severity.value] += 1
        
        # Extract KPI values from metrics
        import_cycles = 0
        doc_coverage = 0.0
        module_density = 0.0
        
        for r in self.results:
            if r.name == "Import Cycles":
                import_cycles = int(r.value) if str(r.value).isdigit() else 0
            elif r.name == "Overall Documentation Coverage":
                # Extract percentage from "67.3% (404/600)"
                import re
                match = re.search(r'([\d.]+)%', str(r.value))
                if match:
                    doc_coverage = float(match.group(1))
            elif r.name == "Module Graph Density":
                module_density = float(r.value) if isinstance(r.value, (int, float)) else 0.0
        
        # Build categories array
        categories_dict = {}
        for r in self.results:
            if r.category not in categories_dict:
                categories_dict[r.category] = {
                    "name": r.category,
                    "severity": "",
                    "metrics": []
                }
            
            # Add metric to category
            metric_value = r.value
            metric_dict = {"name": r.name, "value": metric_value}
            
            # Add detailed data if available
            if r.detailed_data:
                metric_dict["details"] = r.detailed_data
            
            # Extract unit if present (e.g., "8 classes" -> value: 8, unit: "classes")
            if isinstance(metric_value, str):
                parts = str(metric_value).split()
                if len(parts) >= 2 and parts[1] in ['classes', 'modules', 'functions', 'items', 'hops']:
                    try:
                        metric_dict["value"] = int(parts[0])
                        metric_dict["unit"] = parts[1]
                    except ValueError:
                        pass
            
            categories_dict[r.category]["metrics"].append(metric_dict)
        
        # Determine category severity (worst metric in category)
        severity_priority = {
            "critical": 5,
            "warning": 4,
            "acceptable": 3,
            "good": 2,
            "excellent": 1
        }
        
        for category_name in categories_dict:
            worst_severity = "excellent"
            worst_priority = 0
            
            for r in self.results:
                if r.category == category_name:
                    priority = severity_priority.get(r.severity.value, 0)
                    if priority > worst_priority:
                        worst_priority = priority
                        worst_severity = r.severity.value
            
            categories_dict[category_name]["severity"] = worst_severity
        
        # Convert to array and sort by severity (critical first)
        categories_array = list(categories_dict.values())
        categories_array.sort(key=lambda c: severity_priority.get(c["severity"], 0), reverse=True)
        
        # Build top issues from critical and warning metrics
        top_issues = []
        issue_id = 1
        
        for r in self.results:
            if r.severity in [Severity.CRITICAL, Severity.WARNING] and len(top_issues) < 5:
                # Create issue title based on metric
                if r.name == "Import Cycles":
                    title = f"Import cycle detected: {r.value} cycles found"
                elif r.name == "God Classes":
                    title = f"God class detected: {r.value} classes with >20 methods"
                elif "Undocumented" in r.name:
                    title = f"Undocumented public APIs: {r.value} functions without docstrings"
                else:
                    title = f"{r.name}: {r.value}"
                
                # Determine actions based on category
                primary_action = "Fix Guide"
                secondary_action = "View Details"
                
                if "God" in r.name:
                    primary_action = "Refactor"
                    secondary_action = "Analyze"
                elif "Documentation" in r.category:
                    primary_action = "Add Docs"
                    secondary_action = "Ignore"
                elif "Cyclic" in r.category:
                    primary_action = "Fix Guide"
                    secondary_action = "View Code"
                
                issue = {
                    "id": str(issue_id),
                    "title": title,
                    "description": r.description,
                    "severity": r.severity.value,
                    "actions": {
                        "primary": {
                            "label": primary_action,
                            "action": primary_action.lower().replace(" ", "-")
                        },
                        "secondary": {
                            "label": secondary_action,
                            "action": secondary_action.lower().replace(" ", "-")
                        }
                    }
                }
                
                top_issues.append(issue)
                issue_id += 1
        
        # Build final metrics data structure
        metrics_data = {
            "projectId": normalized_name,
            "overallScore": int(round(overall_score)),
            "importCycles": import_cycles,
            "documentationCoverage": round(doc_coverage, 1),
            "moduleDensity": round(module_density, 2),
            "severityDistribution": severity_counts,
            "categories": categories_array,
            "topIssues": top_issues,
            "analyzedAt": datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(metrics_data, f, indent=2)
        
        self.console.print(f"✓ Metrics file exported to [cyan]{filename}[/cyan]", style="green")
        return filename
    
    def _generate_recommendations(self) -> List[Dict[str, str]]:
        """Generate recommendations based on results"""
        recommendations = []
        
        # Check each category for issues
        cycle_issues = [r for r in self.results 
                       if r.category == "Cyclic Dependencies" 
                       and r.severity in [Severity.WARNING, Severity.CRITICAL]]
        if cycle_issues:
            recommendations.append({
                "priority": "CRITICAL",
                "category": "Cyclic Dependencies",
                "action": "Break circular dependencies using Dependency Inversion Principle",
                "reason": "Cycles prevent testing, increase bugs by 2.4x, and block independent development"
            })
        
        god_issues = [r for r in self.results 
                     if r.category == "God Classes/Modules" 
                     and r.severity in [Severity.WARNING, Severity.CRITICAL]]
        if god_issues:
            recommendations.append({
                "priority": "HIGH",
                "category": "God Classes/Modules",
                "action": "Split large classes/modules by responsibility",
                "reason": "Classes with >20 methods have 5x higher defect density"
            })
        
        dead_code = [r for r in self.results 
                    if r.category == "Dead Code" 
                    and r.name == "Potentially Dead Functions"
                    and r.severity in [Severity.ACCEPTABLE, Severity.WARNING]]
        if dead_code:
            recommendations.append({
                "priority": "MEDIUM",
                "category": "Dead Code",
                "action": "Remove unused functions and modules",
                "reason": "Dead code wastes maintenance effort and increases cognitive load"
            })
        
        return recommendations


def run_metrics_analysis(
    target_project: "Path",
    project_name: Optional[str],
    project_graph_name: str,
    output_dir: "Path",
    db_uri: str,
    language: str,
    exclude_patterns: Optional[List[str]],
    entry_points: Optional[List[str]],
    no_default_exclusions: bool,
):
    """
    Run metrics analysis and export results.
    
    Args:
        target_project: Path to the project
        project_name: Project name for output files
        project_graph_name: Project node name in graph
        output_dir: Base output directory
        db_uri: Memgraph connection URI
        language: Programming language
        exclude_patterns: Patterns to exclude from dead code detection
        entry_points: Function names that are entry points
        no_default_exclusions: Don't use default exclusion patterns
    """
    from pathlib import Path
    
    # Determine project name
    if not project_name:
        project_name = target_project.name
    
    # Handle exclusion patterns
    exclude_patterns_final = None
    if no_default_exclusions:
        exclude_patterns_final = exclude_patterns or []
    elif exclude_patterns:
        exclude_patterns_final = MemgraphAnalyzer.DEFAULT_EXCLUDE_PATTERNS + exclude_patterns
    
    # Create analyzer
    analyzer = MemgraphAnalyzer(
        uri=db_uri,
        username="",
        password="",
        project_graph_name=project_graph_name,
        exclude_patterns=exclude_patterns_final,
        entry_points=entry_points,
        language=language
    )
    
    try:
        # Show configuration
        analyzer.console.print(f"\n[cyan]Configuration:[/cyan]")
        analyzer.console.print(f"  Project: [yellow]{project_name}[/yellow]")
        analyzer.console.print(f"  Language: [yellow]{analyzer.language}[/yellow]")
        if analyzer.project_graph_name:
            analyzer.console.print(f"  Graph Filter: [yellow]{analyzer.project_graph_name}[/yellow]")
        analyzer.console.print(f"  Excluding patterns: [yellow]{', '.join(analyzer.exclude_patterns[:5])}{'...' if len(analyzer.exclude_patterns) > 5 else ''}[/yellow]")
        analyzer.console.print(f"  Entry points: [yellow]{', '.join(analyzer.entry_points[:5])}{'...' if len(analyzer.entry_points) > 5 else ''}[/yellow]\n")
        
        # Connect
        if not analyzer.connect():
            sys.exit(1)
        
        # Run analyses
        analyzer.run_all_analyses()
        
        # Print summary
        analyzer.print_summary()
        
        # Normalize project name for folder (use project-id)
        project_id = analyzer._normalize_project_name(project_name)
        
        # Create output directory structure using project-id
        project_output_dir = Path(output_dir) / project_id
        project_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export results
        analyzer.console.print("\n[bold cyan]Exporting results...[/bold cyan]")
        
        # Export project metadata to outputs/[project-name]/project.json
        analyzer.export_project_file(
            project_name=project_name,
            output_path=str(project_output_dir),
            repo_link=str(target_project)
        )
        
        # Export metrics data to outputs/[project-name]/metrics/[date-stamp].json
        analyzer.export_metrics_file(
            project_name=project_name,
            output_path=str(project_output_dir)
        )
        
    except KeyboardInterrupt:
        analyzer.console.print("\n\n[yellow]Analysis interrupted by user[/yellow]")
        raise
    except Exception as e:
        analyzer.console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise
    finally:
        analyzer.close()


def main():
    """Main entry point (for backwards compatibility)"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze code quality metrics in Memgraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
        # Basic usage
        python analyze_quality.py --project-name my-project --project-graph-name MyProject
        
        # JavaScript codebase (filters anonymous functions)
        python analyze_quality.py --project-name my-project --project-graph-name MyProject --language javascript
        
        # Custom exclusions
        python analyze_quality.py --project-name my-project --project-graph-name MyProject --exclude "anonymous_" --exclude "temp_"
        """
    )
    parser.add_argument(
        "--project-name",
        required=True,
        help="Project name (required) - will be used in filenames and project metadata"
    )
    parser.add_argument(
        "--project-graph-name",
        required=True,
        help="Project node name in the knowledge graph (required) - filters all queries to this project"
    )
    parser.add_argument(
        "--output-path",
        default="./outputs",
        help="Base output path (default: ./outputs)"
    )
    parser.add_argument(
        "--uri",
        default="bolt://localhost:7687",
        help="Memgraph connection URI (default: bolt://localhost:7687)"
    )
    parser.add_argument(
        "--language",
        default="javascript",
        choices=["javascript", "python", "java", "csharp", "go", "rust", "generic"],
        help="Programming language for language-specific rules (default: javascript)"
    )
    parser.add_argument(
        "--exclude",
        action="append",
        dest="exclude_patterns",
        help="Pattern to exclude from dead code detection (can be specified multiple times)"
    )
    parser.add_argument(
        "--entry-point",
        action="append",
        dest="entry_points",
        help="Function name that is an entry point (can be specified multiple times)"
    )
    parser.add_argument(
        "--no-default-exclusions",
        action="store_true",
        help="Don't use default exclusion patterns (only use --exclude patterns)"
    )
    
    args = parser.parse_args()
    
    from pathlib import Path
    
    run_metrics_analysis(
        target_project=Path.cwd(),  # Not used in legacy mode
        project_name=args.project_name,
        project_graph_name=args.project_graph_name,
        output_dir=Path(args.output_path),
        db_uri=args.uri,
        language=args.language,
        exclude_patterns=args.exclude_patterns,
        entry_points=args.entry_points,
        no_default_exclusions=args.no_default_exclusions,
    )


if __name__ == "__main__":
    main()
