import redis

from django.conf import settings

# connect to redis
from shop.models import Product

r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB
)


class Recommender:
    def get_product_key(self, id):
        return f'product:{id}:purchased_with'

    def products_bought(self, products):
        product_ids = [p.id for p in products]
        for product_id in product_ids:
            for with_id in product_ids:
                # get the other products bought with each product
                if with_id != product_id:
                    # increment score for product purchased together
                    r.zincrby(self.get_product_key(product_id), 1, with_id)

    def suggest_products_for(self, products, max_results=6):
        product_ids = [p.id for p in products]
        if len(products) == 1:
            # suggestions for only one product
            suggestions = r.zrange(
                self.get_product_key(product_ids[0]),
                0, -1, desc=True)[:max_results]
        else:
            # generate a temporary key
            flat_ids = ''.join([str(id) for id in product_ids])
            temp_key = f'temp_{flat_ids}'
            # multiple products, combine scores of all products
            # store the resulting sorted set in a temporary key
            keys = [self.get_product_key(id) for id in product_ids]
            r.zunionstore(temp_key, keys)
            # remove ids for products the recommendations for
            r.zrem(temp_key, *product_ids)
            # get the products ids by their score, descendant sort
            suggestions = r.zrange(temp_key, 0, -1, desc=True)[:max_results]
            # remove the temporary key
            r.delete(temp_key)

        suggested_products_ids = [int(id) for id in suggestions]
        suggested_products = list(Product.objects.filter(id__in=suggested_products_ids))
        suggested_products.sort(key=lambda x: suggested_products_ids.index(x.id))
        return suggested_products

    def clear_purchases(self):
        for id in Product.objects.values_list('id', flat=True):
            r.delete(self.get_product_key(id))
