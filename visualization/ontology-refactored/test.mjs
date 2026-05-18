import { JSDOM } from 'jsdom';

const url = 'http://localhost:5174/';
JSDOM.fromURL(url, { runScripts: "dangerously", resources: "usable" }).then(dom => {
  dom.window.console.log = (...args) => console.log('PAGE LOG:', ...args);
  dom.window.console.error = (...args) => console.error('PAGE ERROR:', ...args);
  dom.window.console.warn = (...args) => console.warn('PAGE WARN:', ...args);
  dom.window.onerror = (message, source, lineno, colno, error) => {
    console.log('JSDOM error:', message, source, lineno, colno, error);
  };
  
  setTimeout(() => {
    console.log("JSDOM executed");
  }, 2000);
}).catch(err => console.error("Error loading URL:", err));
