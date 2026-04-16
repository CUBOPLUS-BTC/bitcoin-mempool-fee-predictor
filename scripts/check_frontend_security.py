#!/usr/bin/env python3
"""
Frontend Security Check
Verifies frontend dependencies and security configuration
"""

import subprocess
import json
import sys
from pathlib import Path

def run_npm_audit():
    """Run npm audit and return results"""
    frontend_dir = Path(__file__).parent.parent / "frontend-react"
    
    try:
        result = subprocess.run(
            ["npm", "audit", "--json"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("✅ No vulnerabilities found!")
            return True
        
        # Parse audit results
        try:
            audit_data = json.loads(result.stdout)
            vulnerabilities = audit_data.get("vulnerabilities", {})
            
            if not vulnerabilities:
                print("✅ No vulnerabilities found!")
                return True
            
            print(f"\n⚠️  Found {len(vulnerabilities)} vulnerabilities:\n")
            
            for pkg, info in vulnerabilities.items():
                severity = info.get("severity", "unknown")
                via = info.get("via", [])
                
                if isinstance(via, list) and via:
                    title = via[0].get("title", "Unknown issue") if isinstance(via[0], dict) else str(via[0])
                else:
                    title = "Unknown issue"
                
                print(f"  {severity.upper()}: {pkg}")
                print(f"    └─ {title}")
            
            print("\n🔧 To fix, run:")
            print("  cd frontend-react")
            print("  npm audit fix")
            print("  # or if breaking changes are acceptable:")
            print("  npm audit fix --force")
            
            return False
            
        except json.JSONDecodeError:
            # npm audit failed but not in JSON format
            print("⚠️  npm audit found issues:")
            print(result.stdout[:500])
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ npm audit timed out")
        return False
    except FileNotFoundError:
        print("❌ npm not found. Please install Node.js")
        return False
    except Exception as e:
        print(f"❌ Error running npm audit: {e}")
        return False

def check_package_json():
    """Check package.json for security best practices"""
    frontend_dir = Path(__file__).parent.parent / "frontend-react"
    package_json = frontend_dir / "package.json"
    
    if not package_json.exists():
        print("❌ package.json not found")
        return False
    
    with open(package_json) as f:
        pkg = json.load(f)
    
    issues = []
    
    # Check for exact versions in dependencies (should use ^ for flexibility)
    deps = pkg.get("dependencies", {})
    dev_deps = pkg.get("devDependencies", {})
    
    # Check for overrides (good for security)
    overrides = pkg.get("overrides", {})
    if overrides:
        print(f"✅ Found {len(overrides)} package overrides (good for security)")
        for pkg_name, version in overrides.items():
            print(f"   {pkg_name}: {version}")
    
    # Check for audit scripts
    scripts = pkg.get("scripts", {})
    if "audit" in scripts:
        print("✅ 'npm run audit' script available")
    if "audit-fix" in scripts:
        print("✅ 'npm run audit-fix' script available")
    
    return len(issues) == 0

def main():
    print("=" * 60)
    print("🔐 FRONTEND SECURITY CHECK")
    print("=" * 60)
    
    print("\n📦 Checking package.json...")
    check_package_json()
    
    print("\n🔍 Running npm audit...")
    audit_passed = run_npm_audit()
    
    print("\n" + "=" * 60)
    if audit_passed:
        print("✅ Frontend security check PASSED")
    else:
        print("⚠️  Frontend security check found issues")
        print("   Run 'npm audit fix' in frontend-react directory")
    print("=" * 60)
    
    return 0 if audit_passed else 1

if __name__ == "__main__":
    sys.exit(main())
