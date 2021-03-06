# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0008_auto_20150914_1057'),
        ('catalogue', '0009_credit_hours_attr'),
    ]

    operations = [
        migrations.CreateModel(
            name='Catalog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('partner', models.ForeignKey(related_name='catalogs', to='partner.Partner')),
                ('stock_records', models.ManyToManyField(to='partner.StockRecord', blank=True)),
            ],
        ),
    ]
