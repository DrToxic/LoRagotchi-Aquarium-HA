// Optional Playwright browser verification; never connects to a physical radio.
// Usage: PLAYWRIGHT_MODULE=/path/to/playwright CHROMIUM_PATH=/path/to/chrome
// PASSWORD_FILE=/path/to/password node tools/stream_browser_smoke.cjs URL OUTPUT_DIR
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs');const path=require('path');const assert=require('assert');
(async()=>{
 const base=new URL(process.argv[2]);if(!base.pathname.endsWith('/'))throw Error('URL must end in /');
 const output=process.argv[3]||'.local/stream-proof';fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
 try {
  const httpCredentials=process.env.PASSWORD_FILE?{username:'aquarium',password:fs.readFileSync(process.env.PASSWORD_FILE,'utf8').trim()}:undefined;
  const context=await browser.newContext({viewport:{width:1432,height:768},httpCredentials});
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const mode of ['view','control']) {
   const response=await page.goto(new URL(mode+'/',base).href);assert.equal(response.status(),200);
   await page.waitForFunction(()=>document.body.dataset.connected==='true');
   await page.waitForFunction(()=>document.querySelector('canvas')?.width>1);await page.waitForTimeout(900);
   const dimensions=await page.locator('canvas').evaluate(c=>[c.width,c.height]);
   assert.deepEqual(dimensions,mode==='view'?[960,540]:[1432,768]);
   const first=await page.locator('canvas').evaluate(c=>c.toDataURL());await page.waitForTimeout(900);
   assert.notEqual(first,await page.locator('canvas').evaluate(c=>c.toDataURL()),'Rendered scene is not changing');
   await page.screenshot({path:path.join(output,mode+'.png')});
   console.log('PASS',mode,dimensions.join('x'),'and animated pixels');
  }
  // Exercise actual operator pointer delivery, not only WebSocket connectivity.
  await page.mouse.click(1127,72);await page.waitForTimeout(1000);
  await page.screenshot({path:path.join(output,'radio-controls.png')});
  assert.deepEqual(errors,[]);console.log('PASS browser modules/WebSockets at base path',base.pathname);
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
