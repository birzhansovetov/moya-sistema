export type BookStatus = 'want'|'reading'|'finished'|'paused'
export type Book = {id:string;title:string;author:string;pages:number;current_page:number;next_page:number;daily_pages:number;status:BookStatus;start_date:string|null;end_date:string|null;cover_url:string;final_impression:string;deleted:boolean}
export type ReadingLog = {id:string;book_id:string;date:string;page:number|null;chapter:string;text:string;reflection:Record<string,string>;deleted:boolean}
export type PageList<T> = {items:T[];total:number;limit:number;offset:number}
export const bookStatuses:Record<BookStatus,string>={want:'Хочу прочитать',reading:'Читаю',finished:'Прочитал',paused:'Отложил'}
export const reflectionNames:Record<string,string>={read:'Что прочитал',understood:'Что понял своими словами',felt:'Что чувствовал и почему',struck:'Что зацепило',connection:'Связь с моей жизнью',apply:'Что хочу применить'}
