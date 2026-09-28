import asyncio
import os
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

async def record_demo():
    output_dir = Path("recordings")
    output_dir.mkdir(exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(output_dir),
            record_video_size={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        print("1. Navigating to Pantry Chef Agent Frontend...")
        await page.goto("https://pantry-chef-frontend-498613128965.us-east1.run.app/", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        print("2. Executing First Prompt: Check pantry items...")
        # Click the first prompt chip
        await page.click(".chip:has-text('Check my pantry')")
        
        # Wait for agent response bubble (msg.agent)
        print("   Waiting for agent pantry lookup response...")
        await page.wait_for_selector(".msg.agent", timeout=30000)
        await page.wait_for_timeout(4000)
        
        print("3. Executing Second Prompt: Rich Recipe Search + Nutrition + Dish Image...")
        rich_prompt = "Suggest a garlic chicken recipe with nutrition for 2 servings and show me a dish preview image"
        await page.fill("#input", rich_prompt)
        await page.click("button:has-text('Send')")
        
        print("   Waiting for rich agent response with dish image...")
        await page.wait_for_selector(".msg.agent:nth-of-type(2)", timeout=45000)
        await page.wait_for_timeout(6000)
        
        video_obj = page.video
        await context.close()
        await browser.close()
        
        video_path = await video_obj.path()
        print(f"Recorded video raw path: {video_path}")
        
        # Copy to artifacts directory
        artifacts_dir = Path("/config/.gemini/antigravity/brain/4ec0bf6c-2f3e-4cce-974c-ad2116f2ec6e")
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        dest_path = artifacts_dir / "pantry_chef_demo.webm"
        shutil.copy(video_path, dest_path)
        print(f"Copied video to artifact: {dest_path}")

if __name__ == "__main__":
    asyncio.run(record_demo())
