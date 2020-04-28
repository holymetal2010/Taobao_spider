from selenium import webdriver
from loguru import logger
import time
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, WebDriverException
from lxml import etree
from retrying import retry
from selenium.webdriver import ActionChains


class taobao(object):
    def __init__(self):
        self.browser = webdriver.Firefox()
        self.browser.implicitly_wait(5)
        self.domain = 'http://www.taobao.com'
        self.action_chains = ActionChains(self.browser)
        # 处理抓取为空的字段
        self.handleNone = lambda x: x if x else ' '

    def login(self, username, password):
        while True:
            self.browser.get(self.domain)
            time.sleep(1)
            self.browser.find_element_by_class_name('h').click()
            self.browser.find_element_by_id('fm-login-id').send_keys(username)
            self.browser.find_element_by_id('fm-login-password').send_keys(password)
            time.sleep(2)

            try:
                # 出现验证码，滑动验证
                slider = self.browser.find_element_by_xpath("//span[contains(@class, 'btn_slide')]")
                if slider.is_displayed():
                    self.action_chains.drag_and_drop_by_offset(slider, 258, 0).perform()
                    time.sleep(0.5)
                    self.action_chains.release().perform()
            except (NoSuchElementException, WebDriverException):
                logger.info('未出现登录验证码')

            self.browser.find_element_by_class_name('password-login').click()
            nickname = self.get_nickname()
            if nickname:
                logger.info('登录成功，呢称为:' + nickname)
                break
            logger.debug('登录出错，5s后继续登录')
            time.sleep(5)

    def get_product(self, product_name):
        self.browser.get(self.domain)
        self.browser.find_element_by_class_name('search-combobox-input').send_keys(product_name)
        self.browser.find_element_by_xpath(
            "(//button[contains(@class, 'submit')]|//button[contains(@class,'btn-search')])").click()
        # 等待加载
        time.sleep(1)
        self.get_product_detail()

    # 重试3次，间隔1s
    # @retry(stop_max_attempt_number=3, wait_fixed=1000)
    def get_product_detail(self):
        while True:
            try:
                # 模拟往下滚动
                self.drop_down()
                ps = self.browser.page_source
                selector = etree.HTML(ps)
                page = ''.join(selector.xpath("//li[@class='item active']//text()")).strip('\n ')
                items = selector.xpath("//div[@id='mainsrp-itemlist']/div[contains(@class,'m-itemlist')]"
                                       "/div[contains(@class,'grid g-clearfix')]/div[contains(@class,'items')]"
                                       "/div[@class='item J_MouserOnverReq  ']")
                for item in items:
                    price = self.handleNone(''.join(item.xpath(".//div[contains(@class, 'price')]//text()"))).strip()
                    sales = self.handleNone(item.xpath(".//div[@class='deal-cnt']//text()"))[0].replace('人付款', '')
                    title = self.handleNone(''.join(item.xpath(".//div[contains(@class,'row-2')]//text()"))).strip(
                        '\n ')
                    shop_name = self.handleNone(''.join(item.xpath(".//div[contains(@class, 'shop')]//text()"))).strip()
                    location = self.handleNone(''.join(item.xpath(".//div[@class='location']//text()")))
                    logger.info(f"标题:{title}|销量:{sales}|价格:{price}|店名:{shop_name}|商铺地址:{location}")
                logger.info(f'抓取第{page}页完成')

                # 下一页
                next = self.browser.find_element_by_xpath("//li[contains(@class, 'item next')]")
                if 'next-disabled' in next.get_attribute('class'):
                    logger.info('没有下一页，抓取完成')
                    break
                else:
                    # 3.
                    # 这里如果通过click()抛出ElementClickInterceptedException来判断是否出现了验证码似乎会出现以下这种问题
                    # 点击下一页->出现验证码，而此时并不会立即抛出ElementClickInterceptedException
                    # 程序将重新开始一次while循环，并重复抓取本页内容，直到下一次的click()时才会抛出异常
                    # 这样在出现验证码时就会重复抓取数据
                    # 猜想能否在next.click()之后再添加一个动作来判断是否出现了验证码
                    # 另外next好像是关键字
                    next.click()

            # 出现滑块验证
            except ElementClickInterceptedException:
                # 1.
                # 这里的滑块验证位于iframe标签中，无法直接定位，需要通过driver.switch_to.frame()方法切换
                # 并且需要将验证码页面滚动至验证码块可见，再开始模拟滑动，否则会抛出MoveTargetOutOfBoundsException 异常
                # 验证码页面打开时，验证码块恰好不可见（高度相差1），疑为设置的反爬措施
                captcha_frame = self.browser.find_element_by_xpath('//div[@id="J_sufei"]/iframe')
                self.browser.switch_to.frame(captcha_frame)
                slider = self.browser.find_element_by_xpath("//span[contains(@class, 'btn_slide')]")
                # 这里也可以使用self.browser.execute_script('arguments[0].scrollIntoView();', slider)来滑动至 slider可见
                self.drop_down()
                self.action_chains.drag_and_drop_by_offset(slider, 258, 0).perform()
                time.sleep(0.5)
                self.action_chains.release().perform()
                # 2.
                # 这里似乎需要判断验证是否成功，如果验证失败需要点击刷新重新加载并重试
                # 我是通过定义了一个has_element(xpath)的方法来查找出错时的标志性element判断是否验证成功
                # 方法中通过 try:find_element_by_xpath()定位元素，若抛出NoSuchElementException则返回False,否则返回True
                # 但是感觉略显笨拙，代码这里就不提交了，如果有更合适的方法还请指教

                # 滑动完成后需要再将driver切换回原框架中
                self.browser.switch_to.parent_frame()


            except Exception as e:
                logger.error('出现未知错误:' + e)
                self.browser.refresh()
                time.sleep(1)

    # js控制往下拖动
    def drop_down(self):
        for x in range(1, 9):
            time.sleep(0.3)
            j = x / 10
            js = f"document.documentElement.scrollTop = document.documentElement.scrollHeight * {j}"
            self.browser.execute_script(js)
        # 兄地~太快容易出验证码
        time.sleep(2)

    def get_nickname(self):
        self.browser.get(self.domain)
        time.sleep(0.5)
        try:
            return self.browser.find_element_by_class_name('site-nav-user').text
        except NoSuchElementException:
            return ''


if __name__ == '__main__':
    # 填入自己的用户名，密码
    username = 'username'
    password = 'password'
    tb = taobao()
    tb.login(username, password)
    # 可以改成想要商品的名称
    product_name = '零食'
    tb.get_product(product_name)
