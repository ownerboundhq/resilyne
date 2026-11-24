import Stripe from 'stripe';
import {one,tx} from './db.mjs';
export const stripeFor=cfg=>cfg.stripeKey?new Stripe(cfg.stripeKey,{maxNetworkRetries:2,timeout:20000}):null;
export async function checkout(pool,stripe,cfg,account){
 if(!stripe||!cfg.priceId)throw Error('Billing is not configured');
 return tx(pool,async c=>{
   const a=await one(c,'SELECT * FROM accounts WHERE id=$1 FOR UPDATE',[account]);
   let customer=a.stripe_customer;
   if(!customer){
     const item=await stripe.customers.create({metadata:{resilyne_account:String(account)}},{idempotencyKey:'resilyne-customer-'+account});
     customer=item.id;await c.query('UPDATE accounts SET stripe_customer=$2 WHERE id=$1',[account,customer]);
   }
   const subscriptions=await stripe.subscriptions.list({customer,status:'all',limit:20});
   if(subscriptions.data.some(s=>!['canceled','incomplete_expired'].includes(s.status)))return (await stripe.billingPortal.sessions.create({customer,return_url:cfg.origin+'/'})).url;
   const open=await stripe.checkout.sessions.list({customer,status:'open',limit:10});
   if(open.data[0]?.url)return open.data[0].url;
   const session=await stripe.checkout.sessions.create({customer,mode:'subscription',line_items:[{price:cfg.priceId,quantity:1}],success_url:cfg.origin+'/?billing=returned',cancel_url:cfg.origin+'/',client_reference_id:String(account),subscription_data:{metadata:{resilyne_account:String(account)}}});
   return session.url;
 });
}
export async function reconcileBilling(pool,stripe,cfg,event){
 if(!['checkout.session.completed','customer.subscription.created','customer.subscription.updated','customer.subscription.deleted'].includes(event.type))return;
 const object=event.data.object,customer=typeof object.customer==='string'?object.customer:object.customer?.id;
 if(!customer)return;
 await tx(pool,async c=>{
   const a=await one(c,'SELECT * FROM accounts WHERE stripe_customer=$1 FOR UPDATE',[customer]);if(!a)return;
   const seen=await one(c,'INSERT INTO deliveries(id) VALUES($1) ON CONFLICT DO NOTHING RETURNING id',['stripe:'+event.id]);if(!seen)return;
   // Read current subscription state, rather than trusting potentially out-of-order events.
   const all=await stripe.subscriptions.list({customer,status:'all',limit:100});
   const subscriptions=all.data.filter(s=>s.items.data.some(i=>i.price.id===cfg.priceId));
   const sub=subscriptions.find(s=>['active','trialing'].includes(s.status))||subscriptions[0];
   await c.query('UPDATE accounts SET stripe_subscription=$2,billing_status=$3 WHERE id=$1',[a.id,sub?.id||null,sub?.status||'none']);
 });
}
