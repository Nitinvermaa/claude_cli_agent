"""Project scaffolding utilities for language-based app generation."""

from __future__ import annotations

import re
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.console import Console

Language = Literal["python", "javascript", "typescript", "go", "rust", "java"]
Framework = Literal["react", "next", "vue", "svelte", "nuxt", "astro", "express", "fastapi", "spring", "none"]


@dataclass
class ScaffoldRequest:
    language: Language
    name: str
    framework: Framework = "none"
    voice_enabled: bool = False
    vision_enabled: bool = False


TECH_FILE = Path.home() / ".config" / "cagent" / "web_tech_catalog.json"
TECH_PACKAGES = {
    "react": "react",
    "next": "next",
    "vue": "vue",
    "svelte": "svelte",
    "nuxt": "nuxt",
    "astro": "astro",
    "vite": "vite",
    "express": "express",
}


def _safe_name(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-")
    return clean or "generated-app"


def detect_scaffold_request(prompt: str) -> ScaffoldRequest | None:
    text = prompt.lower()
    if "app" not in text and "project" not in text:
        return None
    if not any(token in text for token in ("build", "create", "make", "generate", "scaffold")):
        return None

    language: Language | None = None
    language_map: dict[Language, tuple[str, ...]] = {
        "python": ("python", "fastapi", "flask", "django"),
        "javascript": ("javascript", "js", "node"),
        "typescript": ("typescript", "ts"),
        "go": ("golang", "go"),
        "rust": ("rust",),
        "java": ("java", "spring"),
    }
    for lang, tokens in language_map.items():
        if any(tok in text for tok in tokens):
            language = lang
            break
    if language is None:
        return None

    framework: Framework = "none"
    framework_tokens: dict[Framework, tuple[str, ...]] = {
        "react": ("react", "reactjs"),
        "next": ("next", "nextjs"),
        "vue": ("vue", "vuejs"),
        "svelte": ("svelte",),
        "nuxt": ("nuxt",),
        "astro": ("astro",),
        "express": ("express", "expressjs"),
        "fastapi": ("fastapi",),
        "spring": ("spring", "springboot", "spring-boot"),
        "none": tuple(),
    }
    for fw, tokens in framework_tokens.items():
        if tokens and any(tok in text for tok in tokens):
            framework = fw
            break

    voice_enabled = any(tok in text for tok in ("voice", "speech", "transcribe", "tts", "stt"))
    vision_enabled = any(tok in text for tok in ("vision", "image", "ocr", "multimodal", "vlm"))

    name_match = re.search(r"(?:called|named)\s+([a-zA-Z0-9_-]+)", prompt, flags=re.IGNORECASE)
    name = _safe_name(name_match.group(1)) if name_match else "generated-app"
    return ScaffoldRequest(
        language=language,
        name=name,
        framework=framework,
        voice_enabled=voice_enabled,
        vision_enabled=vision_enabled,
    )


def scaffold_project(cwd: Path, request: ScaffoldRequest, console: Console) -> Path:
    target = cwd / request.name
    target.mkdir(parents=True, exist_ok=True)

    if request.language == "python":
        _scaffold_python(target, request.name, request.framework)
    elif request.language == "javascript":
        _scaffold_javascript(target, request.name, request.framework)
    elif request.language == "typescript":
        _scaffold_typescript(target, request.name, request.framework)
    elif request.language == "go":
        _scaffold_go(target, request.name)
    elif request.language == "rust":
        _scaffold_rust(target, request.name)
    elif request.language == "java":
        _scaffold_java(target, request.name, request.framework)

    if request.voice_enabled:
        _write(
            target / "docs" / "voice.md",
            "# Voice integration\n\nUse STT/TTS providers and add transport APIs for real-time voice.",
        )
    if request.vision_enabled:
        _write(
            target / "docs" / "vision.md",
            "# Vision integration\n\nAdd image upload and VLM analysis pipeline for multimodal workflows.",
        )

    console.print(
        f"[green]Scaffolded {request.language} app:[/green] {target} "
        "(files created so the agent can continue coding directly in project)"
    )
    return target


def refresh_web_tech_catalog() -> dict[str, str]:
    versions: dict[str, str] = {}
    for key, package in TECH_PACKAGES.items():
        url = f"https://registry.npmjs.org/{package}/latest"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            versions[key] = str(payload.get("version", "unknown"))
        except Exception:
            versions[key] = "unknown"
    TECH_FILE.parent.mkdir(parents=True, exist_ok=True)
    TECH_FILE.write_text(json.dumps(versions, indent=2), encoding="utf-8")
    return versions


def load_web_tech_catalog() -> dict[str, str]:
    if not TECH_FILE.exists():
        return refresh_web_tech_catalog()
    try:
        return json.loads(TECH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return refresh_web_tech_catalog()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _scaffold_python(target: Path, name: str, framework: Framework) -> None:
    package_name = name.replace("-", "_")
    if framework == "fastapi":
        _write(
            target / "pyproject.toml",
            f"""[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
]

[project.scripts]
{package_name} = "{package_name}.main:run"
""",
        )
        _write(target / "src" / package_name / "__init__.py", "")
        _write(
            target / "src" / package_name / "main.py",
            f"""from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Generated FastAPI App")


@app.get("/health")
def health() -> dict[str, str]:
    return {{"status": "ok"}}


def run() -> None:
    uvicorn.run("{package_name}.main:app", host="0.0.0.0", port=8000, reload=True)
""",
        )
        _write(
            target / "README.md",
            f"# {name}\n\nGenerated FastAPI scaffold.\n\nRun with `uvicorn {package_name}.main:app --reload`.\n",
        )
        return

    _write(
        target / "pyproject.toml",
        f"""[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []
""",
    )
    _write(target / "src" / package_name / "__init__.py", "")
    _write(
        target / "src" / package_name / "main.py",
        """def main() -> None:
    print("Hello from generated python app")


if __name__ == "__main__":
    main()
""",
    )
    _write(target / "README.md", f"# {name}\n\nGenerated Python app scaffold.\n")


def _scaffold_javascript(target: Path, name: str, framework: Framework) -> None:
    versions = load_web_tech_catalog()
    if framework == "express":
        _write(
            target / "package.json",
            f"""{{
  "name": "{name}",
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "start": "node src/index.js"
  }},
  "dependencies": {{
    "express": "^{versions.get("express", "4.21.2")}"
  }}
}}
""",
        )
        _write(
            target / "src" / "index.js",
            """import express from "express";

const app = express();
const port = Number(process.env.PORT ?? 3000);

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.listen(port, () => {
  console.log(`Express app listening on port ${port}`);
});
""",
        )
        _write(target / "README.md", f"# {name}\n\nGenerated Express.js scaffold.\n")
        return

    framework_hint = f"Framework target: {framework}" if framework != "none" else "No framework selected"
    _write(
        target / "package.json",
        f"""{{
  "name": "{name}",
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "start": "node src/index.js"
  }}
}}
""",
    )
    _write(target / "src" / "index.js", 'console.log("Hello from generated JavaScript app");\n')
    _write(
        target / "README.md",
        f"# {name}\n\nGenerated JavaScript app scaffold.\n\n{framework_hint}\n\nKnown web versions: {versions}\n",
    )


def _scaffold_typescript(target: Path, name: str, framework: Framework) -> None:
    versions = load_web_tech_catalog()
    if framework == "next":
        _write(
            target / "package.json",
            f"""{{
  "name": "{name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  }},
  "dependencies": {{
    "next": "^{versions.get("next", "latest")}",
    "react": "^{versions.get("react", "latest")}",
    "react-dom": "^{versions.get("react", "latest")}"
  }},
  "devDependencies": {{
    "typescript": "^5.6.0",
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0"
  }}
}}
""",
        )
        _write(
            target / "tsconfig.json",
            """{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
""",
        )
        _write(target / "next-env.d.ts", '/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n')
        _write(
            target / "app" / "layout.tsx",
            """import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
""",
        )
        _write(
            target / "app" / "page.tsx",
            """export default function HomePage() {
  return <main>Generated Next.js app</main>;
}
""",
        )
        _write(target / "README.md", f"# {name}\n\nGenerated Next.js (TypeScript) scaffold.\n")
        return

    if framework == "react":
        _write(
            target / "package.json",
            f"""{{
  "name": "{name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "react": "^{versions.get("react", "latest")}",
    "react-dom": "^{versions.get("react", "latest")}"
  }},
  "devDependencies": {{
    "typescript": "^5.6.0",
    "vite": "^{versions.get("vite", "latest")}",
    "@vitejs/plugin-react": "^4.3.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0"
  }}
}}
""",
        )
        _write(
            target / "tsconfig.json",
            """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "jsx": "react-jsx",
    "strict": true,
    "moduleResolution": "bundler"
  },
  "include": ["src"]
}
""",
        )
        _write(
            target / "vite.config.ts",
            """import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
});
""",
        )
        _write(
            target / "index.html",
            """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Generated React App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""",
        )
        _write(target / "src" / "App.tsx", 'export default function App() {\n  return <h1>Generated React app</h1>;\n}\n')
        _write(
            target / "src" / "main.tsx",
            """import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
""",
        )
        _write(target / "README.md", f"# {name}\n\nGenerated React (TypeScript + Vite) scaffold.\n")
        return

    if framework == "vue":
        _write(
            target / "package.json",
            f"""{{
  "name": "{name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "vue": "^{versions.get("vue", "latest")}"
  }},
  "devDependencies": {{
    "typescript": "^5.6.0",
    "vite": "^{versions.get("vite", "latest")}",
    "@vitejs/plugin-vue": "^5.1.0"
  }}
}}
""",
        )
        _write(
            target / "vite.config.ts",
            """import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
});
""",
        )
        _write(
            target / "tsconfig.json",
            """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "strict": true,
    "moduleResolution": "bundler"
  },
  "include": ["src"]
}
""",
        )
        _write(
            target / "index.html",
            """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Generated Vue App</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
""",
        )
        _write(
            target / "src" / "App.vue",
            """<template>
  <main>Generated Vue app</main>
</template>
""",
        )
        _write(
            target / "src" / "main.ts",
            """import { createApp } from "vue";
import App from "./App.vue";

createApp(App).mount("#app");
""",
        )
        _write(target / "README.md", f"# {name}\n\nGenerated Vue (TypeScript + Vite) scaffold.\n")
        return

    if framework == "astro":
        _write(
            target / "package.json",
            f"""{{
  "name": "{name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview"
  }},
  "dependencies": {{
    "astro": "^{versions.get("astro", "latest")}"
  }}
}}
""",
        )
        _write(target / "astro.config.mjs", 'import { defineConfig } from "astro/config";\n\nexport default defineConfig({});\n')
        _write(
            target / "src" / "pages" / "index.astro",
            """---
const title = "Generated Astro app";
---

<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{title}</title>
  </head>
  <body>
    <main>{title}</main>
  </body>
</html>
""",
        )
        _write(target / "README.md", f"# {name}\n\nGenerated Astro scaffold.\n")
        return

    framework_hint = f"Framework target: {framework}" if framework != "none" else "No framework selected"
    _write(
        target / "package.json",
        f"""{{
  "name": "{name}",
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "build": "tsc",
    "start": "node dist/index.js"
  }},
  "devDependencies": {{
    "typescript": "^5.6.0"
  }}
}}
""",
    )
    _write(
        target / "tsconfig.json",
        """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true
  }
}
""",
    )
    _write(target / "src" / "index.ts", 'console.log("Hello from generated TypeScript app");\n')
    _write(
        target / "README.md",
        f"# {name}\n\nGenerated TypeScript app scaffold.\n\n{framework_hint}\n\nKnown web versions: {versions}\n",
    )


def _scaffold_go(target: Path, name: str) -> None:
    _write(target / "go.mod", f"module {name}\n\ngo 1.22\n")
    _write(
        target / "main.go",
        """package main

import "fmt"

func main() {
    fmt.Println("Hello from generated Go app")
}
""",
    )
    _write(target / "README.md", f"# {name}\n\nGenerated Go app scaffold.\n")


def _scaffold_rust(target: Path, name: str) -> None:
    _write(
        target / "Cargo.toml",
        f"""[package]
name = "{name}"
version = "0.1.0"
edition = "2021"
""",
    )
    _write(
        target / "src" / "main.rs",
        """fn main() {
    println!("Hello from generated Rust app");
}
""",
    )
    _write(target / "README.md", f"# {name}\n\nGenerated Rust app scaffold.\n")


def _scaffold_java(target: Path, name: str, framework: Framework) -> None:
    if framework == "spring":
        _write(
            target / "pom.xml",
            """<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.5.0</version>
    <relativePath/>
  </parent>
  <groupId>com.example</groupId>
  <artifactId>app</artifactId>
  <version>0.1.0</version>
  <properties>
    <java.version>17</java.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>
    </plugins>
  </build>
</project>
""",
        )
        _write(
            target / "src" / "main" / "java" / "com" / "example" / "Application.java",
            """package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}

@RestController
class HealthController {
    @GetMapping("/health")
    public String health() {
        return "ok";
    }
}
""",
        )
        _write(target / "README.md", f"# {name}\n\nGenerated Spring Boot scaffold.\n")
        return

    _write(
        target / "pom.xml",
        """<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>app</artifactId>
  <version>0.1.0</version>
</project>
""",
    )
    _write(
        target / "src" / "main" / "java" / "com" / "example" / "App.java",
        """package com.example;

public class App {
    public static void main(String[] args) {
        System.out.println("Hello from generated Java app");
    }
}
""",
    )
    _write(target / "README.md", f"# {name}\n\nGenerated Java app scaffold.\n")
