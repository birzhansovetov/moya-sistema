import {AppIcon} from '../components/AppIcon'
import {Link} from 'react-router-dom'
import styles from './Health.module.css'

export function HealthPage(){
 const areas=[
  {id:'sport',index:'01',title:'Спорт',description:'Подберите тренировку, изучайте технику и записывайте результаты.',meta:'Программа и журнал',to:'/health/sport'},
  {id:'nutrition',index:'02',title:'Питание',description:'Выбирайте рецепты и рассчитывайте граммы на нужное число порций.',meta:'Рецепты и приготовление',to:'/health/nutrition'},
  {id:'calories',index:'03',title:'Калькулятор калорий',description:'Получите ориентир по возрасту, росту, весу и активности.',meta:'Личный расчёт',to:'/health/calories'},
 ]
 return <div className={styles.page}>
  <div className="pageHeader"><div><Link className="textButton" to="/sections">Все сферы</Link><h1>Здоровье</h1><p>Выберите тренировку, рецепт или расчёт калорий.</p></div></div>
  <div className={styles.grid}>{areas.map(area=><Link className={`${styles.card} ${styles[area.id]}`} to={area.to} key={area.id}><div className={styles.top}><AppIcon name="health"/><span>{area.meta}</span></div><div><h2>{area.title}</h2><p>{area.description}</p></div><span className={styles.action}>Открыть {area.id==='calories'?'расчёт':area.title.toLowerCase()}</span></Link>)}</div>
 </div>
}
