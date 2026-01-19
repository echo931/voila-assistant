"""Tests pour les modèles de données"""

import pytest
from decimal import Decimal
from src.models import Product, CartItem, Cart


class TestProduct:
    """Tests pour la classe Product"""
    
    def test_from_api_response_basic(self):
        """Test création depuis réponse API"""
        data = {
            'id': 'test-123',
            'name': 'Lait 2%',
            'brand': 'Natrel',
            'size': {'value': '2L'},
            'price': {
                'current': {'amount': '5.49', 'currency': 'CAD'},
                'unit': {
                    'label': 'fop.price.per.100ml',
                    'current': {'amount': '0.27', 'currency': 'CAD'}
                }
            },
            'status': 'AVAILABLE'
        }
        
        product = Product.from_api_response(data)
        
        assert product.id == 'test-123'
        assert product.name == 'Lait 2%'
        assert product.brand == 'Natrel'
        assert product.size == '2L'
        assert product.price == Decimal('5.49')
        assert product.unit_price == Decimal('0.27')
        assert product.available is True
    
    def test_from_api_response_minimal(self):
        """Test avec données minimales"""
        data = {
            'id': 'test-456',
            'name': 'Bananes',
            'price': {
                'current': {'amount': '2.99', 'currency': 'CAD'}
            }
        }
        
        product = Product.from_api_response(data)
        
        assert product.id == 'test-456'
        assert product.name == 'Bananes'
        assert product.brand is None
        assert product.size is None
        assert product.price == Decimal('2.99')
    
    def test_format_table_row(self):
        """Test formatage ligne de table"""
        product = Product(
            id='test',
            name='Pain blanc',
            size='675g',
            price=Decimal('3.99'),
            unit_price=Decimal('0.59'),
            unit_label='100g'
        )
        
        row = product.format_table_row()
        
        assert 'Pain blanc' in row
        assert '$3.99' in row


class TestCart:
    """Tests pour la classe Cart"""
    
    def test_empty_cart(self):
        """Test panier vide"""
        cart = Cart(id='test', items=[], subtotal=Decimal('0'))
        
        assert cart.item_count == 0
        assert cart.subtotal == Decimal('0')
        assert cart.is_above_minimum is False
    
    def test_cart_with_items(self):
        """Test panier avec articles"""
        items = [
            CartItem(
                product_id='p1',
                product_name='Lait',
                quantity=2,
                unit_price=Decimal('5.49'),
                total_price=Decimal('10.98')
            ),
            CartItem(
                product_id='p2',
                product_name='Pain',
                quantity=1,
                unit_price=Decimal('3.99'),
                total_price=Decimal('3.99')
            )
        ]
        
        cart = Cart(id='test', items=items, subtotal=Decimal('14.97'))
        
        assert cart.item_count == 3
        assert cart.subtotal == Decimal('14.97')
        assert cart.is_above_minimum is False  # < 35$
    
    def test_cart_above_minimum(self):
        """Test panier au-dessus du minimum"""
        items = [
            CartItem(
                product_id='p1',
                product_name='Groceries',
                quantity=1,
                unit_price=Decimal('40.00'),
                total_price=Decimal('40.00')
            )
        ]
        
        cart = Cart(id='test', items=items, subtotal=Decimal('40.00'))
        
        assert cart.is_above_minimum is True
    
    def test_format_summary(self):
        """Test formatage résumé"""
        items = [
            CartItem(
                product_id='p1',
                product_name='Lait',
                quantity=1,
                unit_price=Decimal('5.49'),
                total_price=Decimal('5.49')
            )
        ]
        
        cart = Cart(id='test', items=items, subtotal=Decimal('5.49'))
        summary = cart.format_summary()
        
        assert '🛒 Panier' in summary
        assert 'Lait' in summary
        assert '$5.49' in summary


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
